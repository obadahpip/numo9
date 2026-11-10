import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

/**
 * A-10-T18 — visual regression for every @numo9/ui story (Playwright screenshots against the
 * built Storybook). The story list comes from `storybook-static/index.json`, so a new story is
 * covered as soon as it exists; tag a story `no-visual` to leave it out (none are today).
 *
 * Baselines: `e2e/__screenshots__/visual.spec.ts/<story-id>.png`, Linux + Chromium + Inter.
 * Update after an intended change and review the PNG diff in the pull request:
 *   pnpm --filter @numo9/ui run test:visual:update
 */
interface IndexEntry {
  id: string;
  type: "story" | "docs";
  title: string;
  name: string;
  tags?: string[];
}

const index = JSON.parse(
  readFileSync(fileURLToPath(new URL("../storybook-static/index.json", import.meta.url)), "utf8"),
) as { entries: Record<string, IndexEntry> };

const STORIES = Object.values(index.entries).filter(
  (entry) => entry.type === "story" && !entry.tags?.includes("no-visual"),
);

/** Fixed clock: date pickers and "today" shortcuts render the same day on every run. */
const FIXED_NOW = new Date("2026-10-26T14:00:00-04:00");

test.describe("@visual components", () => {
  test.use({ viewport: { width: 1024, height: 768 } });

  test("every story is covered", () => {
    expect(STORIES.length).toBeGreaterThanOrEqual(40);
  });

  for (const story of STORIES) {
    test(`${story.title} › ${story.name}`, async ({ page }) => {
      await page.clock.setFixedTime(FIXED_NOW);
      await page.goto(`/iframe.html?id=${story.id}&viewMode=story`);
      await expect(page.locator("#storybook-root > *").first()).toBeAttached();
      await page.evaluate(() => document.fonts.ready);
      await expect(page).toHaveScreenshot(`${story.id}.png`);
    });
  }
});
