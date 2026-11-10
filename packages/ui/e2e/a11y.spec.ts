import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

import { auditLabels, blocking, describeFindings, runAxe } from "./a11y";

/**
 * A-10-T19 — accessibility of every @numo9/ui story in a real browser (gap-60):
 * axe-core with 0 serious/critical violations (contrast included) and the hidden-label audit.
 * Landmark and page-heading rules are off here: a story renders one component on its own; the
 * page suite (frontend/e2e/a11y.spec.ts) checks them on real routes.
 */
interface IndexEntry {
  id: string;
  type: "story" | "docs";
  title: string;
  name: string;
}

const index = JSON.parse(
  readFileSync(fileURLToPath(new URL("../storybook-static/index.json", import.meta.url)), "utf8"),
) as { entries: Record<string, IndexEntry> };
const STORIES = Object.values(index.entries).filter((e) => e.type === "story");

const COMPONENT_ONLY = ["region", "landmark-one-main", "page-has-heading-one"];

test.describe("a11y components", () => {
  test.use({ viewport: { width: 1024, height: 768 } });

  test("every story is checked", () => {
    expect(STORIES.length).toBeGreaterThanOrEqual(40);
  });

  test("gap-60: the label audit catches a leaked hidden header", async ({ page }) => {
    await page.setContent(`
      <style>.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}</style>
      <table><thead><tr>
        <th>Variance <span class="sr-only">Variance</span></th>
        <th aria-label="Amount for Amount">Amount</th>
        <th><span class="sr-only">Actions</span></th>
        <th></th>
      </tr></thead></table>
      <p class="sr-only" style="clip:auto;width:auto;height:auto;position:static">Leaked label</p>`);
    const problems = await auditLabels(page);
    expect(problems.map((p) => p.rule).sort()).toEqual([
      "empty-name",
      "header-repeats-hidden-text", // "Variance" + hidden "Variance"
      "repeated-name", // "Variance Variance"
      "repeated-name", // "Amount for Amount"
      "visible-sr-only",
    ]);
  });

  for (const story of STORIES) {
    test(`${story.title} › ${story.name}`, async ({ page }) => {
      await page.goto(`/iframe.html?id=${story.id}&viewMode=story`);
      await expect(page.locator("#storybook-root > *").first()).toBeAttached();
      await page.evaluate(() => document.fonts.ready);

      const findings = await runAxe(page, { disableRules: COMPONENT_ONLY });
      for (const f of findings.filter((x) => !blocking([x]).length)) {
        test
          .info()
          .annotations.push({ type: `axe ${f.impact}`, description: `${f.id}: ${f.help}` });
      }
      expect(blocking(findings), describeFindings(blocking(findings))).toEqual([]);
      expect(await auditLabels(page)).toEqual([]);
    });
  }
});
