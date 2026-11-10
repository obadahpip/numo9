#!/usr/bin/env node
/**
 * build-tokens (A-10-T03): tokens/tokens.json (W3C DTCG) → CSS.
 *
 *   node scripts/build-tokens.mjs           write src/styles/tokens.css and src/styles/theme.css
 *   node scripts/build-tokens.mjs --check   exit 1 if the committed files differ from tokens.json
 *
 * tokens.css  `:root` custom properties `--n9-*`. Semantic tokens reference the primitives with
 *             `var()`, so a theme (dark mode later) overrides the semantic layer only.
 * theme.css   Tailwind v4 `@theme inline` block mapping Tailwind's namespaces (colours, fonts, text
 *             sizes, radius, shadows, spacing, breakpoints) to the `--n9-*` properties. Tailwind's
 *             default colour palette and breakpoints are removed, so only token values exist.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { flatten, renderThemeCss, renderTokensCss } from "./tokens-lib.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
export const TOKENS_FILE = join(ROOT, "tokens", "tokens.json");
export const TOKENS_CSS = join(ROOT, "src", "styles", "tokens.css");
export const THEME_CSS = join(ROOT, "src", "styles", "theme.css");

export function loadTokens(file = TOKENS_FILE) {
  return flatten(JSON.parse(readFileSync(file, "utf8")));
}

export function build({ check = false } = {}) {
  const tokens = loadTokens();
  const outputs = [
    [TOKENS_CSS, renderTokensCss(tokens)],
    [THEME_CSS, renderThemeCss(tokens)],
  ];
  const stale = [];
  for (const [file, content] of outputs) {
    let current = null;
    try {
      current = readFileSync(file, "utf8");
    } catch {
      current = null;
    }
    if (current === content) continue;
    if (check) stale.push(file);
    else writeFileSync(file, content);
  }
  return { tokens: tokens.length, stale };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const check = process.argv.includes("--check");
  const { tokens, stale } = build({ check });
  if (stale.length) {
    console.error(
      `build-tokens: generated CSS is out of date with tokens.json:\n  ${stale.join("\n  ")}\n` +
        "Run: pnpm --filter @numo9/ui run tokens",
    );
    process.exit(1);
  }
  console.log(`build-tokens: ${tokens} tokens ${check ? "— generated CSS up to date" : "written"}`);
}
