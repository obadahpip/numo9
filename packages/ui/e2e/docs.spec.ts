import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

import { blocking, describeFindings, runAxe } from "./a11y";

/**
 * A-10-T20 — the Storybook usage docs are published: every page under "Guidelines" renders in the
 * built Storybook without script errors, has its title, the do / don't pairs, its embedded
 * stories and no serious accessibility violations.
 */
interface IndexEntry {
  id: string;
  type: "story" | "docs";
  title: string;
}

const index = JSON.parse(
  readFileSync(fileURLToPath(new URL("../storybook-static/index.json", import.meta.url)), "utf8"),
) as { entries: Record<string, IndexEntry> };
const DOCS = Object.values(index.entries).filter(
  (e) => e.type === "docs" && e.title.startsWith("Guidelines/"),
);

test("the usage docs are in the built Storybook", () => {
  expect(DOCS.map((d) => d.title).sort()).toEqual([
    "Guidelines/Data grids",
    "Guidelines/Forms and pickers",
    "Guidelines/Introduction",
    "Guidelines/Layout",
    "Guidelines/Microcopy",
    "Guidelines/Primitives",
    "Guidelines/States",
  ]);
});

for (const doc of DOCS) {
  test(`${doc.title} renders`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(`/iframe.html?id=${doc.id}&viewMode=docs`);
    await expect(page.locator(".sbdocs-content h1").first()).toBeVisible();
    if (!doc.title.endsWith("Introduction")) {
      await expect(page.getByRole("region", { name: "Do", exact: true }).first()).toBeVisible();
      await expect(page.getByRole("region", { name: "Don't", exact: true }).first()).toBeVisible();
    }
    // Embedded stories render (Microcopy and Introduction embed none).
    if (!/Introduction|Microcopy/.test(doc.title)) {
      await expect(page.locator(".docs-story").first()).toBeVisible();
    }
    const findings = blocking(
      await runAxe(page, { disableRules: ["region", "landmark-one-main", "page-has-heading-one"] }),
    );
    expect(findings, describeFindings(findings)).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test("Microcopy lists the eight rules and the reference messages", async ({ page }) => {
  await page.goto("/iframe.html?id=guidelines-microcopy--docs&viewMode=docs");
  const content = page.locator(".sbdocs-content");
  await expect(content.locator("ol > li")).toHaveCount(8);
  await expect(content).toContainText("Buttons are verbs");
  await expect(content).toContainText('Never "Oops"');
  await expect(content).toContainText("before the General Ledger lock date (30 Jun 2026)");
  await expect(content).toContainText("'M5V2T' is missing a character");
});
