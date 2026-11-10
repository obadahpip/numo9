import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

import type { Page } from "@playwright/test";

/**
 * Browser accessibility checks (A-10-T19, gap-60), shared by the component suite
 * (packages/ui/e2e/a11y.spec.ts) and the page suite (frontend/e2e/a11y.spec.ts).
 *
 * 1. `runAxe` — axe-core in a real browser (WCAG 2.0/2.1 A + AA and best practices, colour
 *    contrast included, which jsdom cannot compute).
 * 2. `auditLabels` — the "leaked hidden header" audit behind gap-60: Xero's Executive Summary
 *    prints the hidden column header "Variance for Variance". Checked on every screen:
 *    - screen-reader-only text (`.sr-only`) is visually hidden unless it has focus;
 *    - no accessible name repeats itself ("Variance for Variance", "Amount Amount");
 *    - a header's screen-reader-only text does not repeat its visible text;
 *    - every column/row header and every `aria-label` has a non-empty name.
 */
const AXE_PATH = createRequire(import.meta.url).resolve("axe-core/axe.min.js");
let axeSource: string | undefined;

export const BLOCKING_IMPACTS = ["serious", "critical"] as const;

export interface AxeFinding {
  id: string;
  impact: string;
  help: string;
  targets: string[];
}

export interface AxeOptions {
  /** axe rules to switch off, e.g. landmark rules for a component rendered on its own. */
  disableRules?: string[];
  /** Scope (CSS selector); default the whole document. */
  include?: string;
}

/** All axe violations, worst first. */
export async function runAxe(page: Page, options: AxeOptions = {}): Promise<AxeFinding[]> {
  axeSource ??= readFileSync(AXE_PATH, "utf8");
  const findings = await page.evaluate(
    async ({ source, disableRules, include }) => {
      // A private axe-core instance (this repository's pinned version), separate from any axe
      // the page already loaded (Storybook's a11y addon runs its own copy in the story window).
      type Axe = typeof import("axe-core");
      const holder = window as unknown as { __numo9Axe?: Axe };
      if (!holder.__numo9Axe) {
        const module = { exports: {} as Axe };
        // eslint-disable-next-line @typescript-eslint/no-implied-eval
        new Function("module", "exports", "define", `${source}\n;`)(
          module,
          module.exports,
          undefined,
        );
        holder.__numo9Axe = module.exports;
      }
      const axe = holder.__numo9Axe;
      const rules = Object.fromEntries(disableRules.map((id) => [id, { enabled: false }]));
      const result = await axe.run(include ? { include: [include] } : document, {
        runOnly: {
          type: "tag",
          values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"],
        },
        rules,
        resultTypes: ["violations"],
      });
      return result.violations.map((v) => ({
        id: v.id,
        impact: v.impact ?? "minor",
        help: v.help,
        targets: v.nodes.map((node) => node.target.join(" ")),
      }));
    },
    { source: axeSource, disableRules: options.disableRules ?? [], include: options.include ?? "" },
  );
  const rank = (impact: string) => ["critical", "serious", "moderate", "minor"].indexOf(impact);
  return findings.sort((a, b) => rank(a.impact) - rank(b.impact));
}

export function blocking(findings: AxeFinding[]): AxeFinding[] {
  return findings.filter((f) => (BLOCKING_IMPACTS as readonly string[]).includes(f.impact));
}

export function describeFindings(findings: AxeFinding[]): string {
  return findings
    .map((f) => `${f.id} (${f.impact}): ${f.help}\n    ${f.targets.join("\n    ")}`)
    .join("\n");
}

export interface LabelProblem {
  rule: "visible-sr-only" | "repeated-name" | "header-repeats-hidden-text" | "empty-name";
  target: string;
  text: string;
}

/** gap-60 audit of hidden labels and accessible names; returns every problem found. */
export async function auditLabels(page: Page, scope = "body"): Promise<LabelProblem[]> {
  return page.evaluate((scopeSelector) => {
    const root = document.querySelector(scopeSelector) ?? document.body;
    const problems: { rule: string; target: string; text: string }[] = [];
    const clean = (text: string | null | undefined) => (text ?? "").replace(/\s+/g, " ").trim();
    const describe = (el: Element) => {
      const id = el.id ? `#${el.id}` : "";
      const cls =
        typeof el.className === "string" && el.className ? `.${el.className.split(" ")[0]}` : "";
      return `${el.tagName.toLowerCase()}${id}${cls}`;
    };
    const repeated = (name: string) => {
      const forMatch = /^(.+?) for \1$/i.exec(name);
      if (forMatch) return true;
      const words = name.split(" ");
      if (words.length % 2 === 0 && words.length > 0) {
        const half = words.length / 2;
        if (
          words.slice(0, half).join(" ").toLowerCase() === words.slice(half).join(" ").toLowerCase()
        ) {
          return true;
        }
      }
      return false;
    };
    const visuallyHidden = (el: HTMLElement) => {
      const style = getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden") return true;
      const rect = el.getBoundingClientRect();
      if (rect.width <= 1 && rect.height <= 1) return true;
      const clip = style.clip;
      if (clip && clip !== "auto" && /rect\(0(px)?,? 0(px)?,? 0(px)?,? 0(px)?\)/.test(clip))
        return true;
      if (style.clipPath && style.clipPath.startsWith("inset(50%")) return true;
      return false;
    };
    const visibleText = (el: Element): string => {
      let text = "";
      for (const node of Array.from(el.childNodes)) {
        if (node.nodeType === Node.TEXT_NODE) text += node.textContent ?? "";
        else if (node instanceof HTMLElement) {
          if (node.classList.contains("sr-only") || node.getAttribute("aria-hidden") === "true")
            continue;
          if (!visuallyHidden(node)) text += ` ${visibleText(node)}`;
        }
      }
      return clean(text);
    };
    const hiddenText = (el: Element) =>
      clean(
        Array.from(el.querySelectorAll(".sr-only"))
          .map((n) => n.textContent)
          .join(" "),
      );

    // 1. Screen-reader-only text must not be visible (unless it is the focused skip link).
    for (const el of Array.from(root.querySelectorAll<HTMLElement>(".sr-only"))) {
      if (el === document.activeElement || el.contains(document.activeElement)) continue;
      if (!visuallyHidden(el)) {
        problems.push({
          rule: "visible-sr-only",
          target: describe(el),
          text: clean(el.textContent),
        });
      }
    }
    // 2. Accessible names given by aria-label or hidden text must be non-empty and not repeat.
    for (const el of Array.from(root.querySelectorAll<HTMLElement>("[aria-label]"))) {
      const name = clean(el.getAttribute("aria-label"));
      if (!name) problems.push({ rule: "empty-name", target: describe(el), text: "" });
      else if (repeated(name))
        problems.push({ rule: "repeated-name", target: describe(el), text: name });
    }
    // 3. Headers: a name, no self-repetition, hidden text not repeating the visible text.
    const headers = root.querySelectorAll<HTMLElement>("th, [role=columnheader], [role=rowheader]");
    for (const header of Array.from(headers)) {
      if (header.closest("[aria-hidden=true]")) continue;
      const visible = visibleText(header);
      const hidden = hiddenText(header);
      const aria = clean(header.getAttribute("aria-label"));
      const labelledBy = clean(
        (header.getAttribute("aria-labelledby") ?? "")
          .split(" ")
          .map((id) => document.getElementById(id)?.textContent ?? "")
          .join(" "),
      );
      const name = labelledBy || aria || clean(`${visible} ${hidden}`);
      const hasControlName = header.querySelector(
        "input[aria-label], button[aria-label], [role=checkbox][aria-label]",
      );
      if (!name && !hasControlName) {
        problems.push({ rule: "empty-name", target: describe(header), text: "" });
        continue;
      }
      if (name && repeated(name)) {
        problems.push({ rule: "repeated-name", target: describe(header), text: name });
      }
      if (visible && hidden && hidden.toLowerCase().includes(visible.toLowerCase())) {
        problems.push({
          rule: "header-repeats-hidden-text",
          target: describe(header),
          text: `${visible} | ${hidden}`,
        });
      }
    }
    const seen = new Set<string>();
    return problems.filter((p) => {
      const key = `${p.rule}|${p.target}|${p.text}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, scope) as Promise<LabelProblem[]>;
}
