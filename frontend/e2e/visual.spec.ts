import { expect, test } from "@playwright/test";

import { GAP_02_PATHS } from "./gap-02.paths";

/**
 * A-10-T18 — visual regression for the Phase 0 pages (Playwright screenshots of the production
 * build): the organisation home "/", every Phase 0 organisation route and the 404 page, at
 * desktop (1280 px) and phone (360 px) width.
 *
 * Baselines: `e2e/__screenshots__/visual.spec.ts/<page>-<width>.png` (Linux + Chromium + Inter).
 * Update after an intended change and review the PNG diff in the pull request:
 *   pnpm --filter @numo9/frontend run test:visual:update
 */
const ORG_ROUTES = [
  ...new Set(GAP_02_PATHS.map((p) => p.final).filter((f) => f.startsWith("/o/"))),
];
const PAGES: { name: string; path: string }[] = [
  { name: "home", path: "/" },
  ...ORG_ROUTES.map((path) => ({ name: path.slice(1).replaceAll("/", "_"), path })),
  { name: "not-found", path: "/o/acme/no-such-screen" },
];
const WIDTHS = [
  { width: 1280, height: 800 },
  { width: 360, height: 740 },
] as const;

const FIXED_NOW = new Date("2026-10-26T14:00:00-04:00");

test.describe("@visual pages", () => {
  test("every Phase 0 organisation route is covered", () => {
    expect(ORG_ROUTES.length).toBeGreaterThanOrEqual(8);
  });

  for (const viewport of WIDTHS) {
    test.describe(`${viewport.width} px`, () => {
      test.use({ viewport });

      for (const { name, path } of PAGES) {
        test(`${path}`, async ({ page }) => {
          await page.clock.setFixedTime(FIXED_NOW);
          await page.goto(path);
          await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
          await page.evaluate(() => document.fonts.ready);
          await expect(page).toHaveScreenshot(`${name}-${viewport.width}.png`, { fullPage: true });
        });
      }
    });
  }
});
