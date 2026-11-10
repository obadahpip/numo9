import { expect, test } from "@playwright/test";

import { GAP_02_PATHS } from "./gap-02.paths";

/**
 * gap-12 (A-10-T17): no promotional or announcement banners inside work screens, and nothing
 * pushes the screen's content below the fold. On every Phase 0 organisation route:
 * - the only `banner` landmark is the app shell's top bar;
 * - no element carries a banner/promo class or data attribute;
 * - the page heading sits in the first 200 px of the main region at 1280 × 800.
 * The lint half of gap-12 is `numo9/no-work-screen-banners` (src/lint/*.test.ts).
 */
const ROUTES = [...new Set(GAP_02_PATHS.map((p) => p.final).filter((f) => f.startsWith("/o/")))];

const PROMO_SELECTOR =
  "[data-banner], [data-promo], [class~='banner'], [class~='promo'], [class~='upsell'], " +
  "[class*='-banner'], [class*='promo-'], [class*='upsell-']";

test.use({ viewport: { width: 1280, height: 800 } });

test("the gap-12 check detects an injected promotional banner", async ({ page }) => {
  await page.goto(ROUTES[0]!);
  await page.getByRole("main").evaluate((main) => {
    const promo = document.createElement("div");
    promo.className = "promo-banner";
    promo.setAttribute("role", "banner");
    main.prepend(promo);
  });
  expect(await page.locator(PROMO_SELECTOR).count()).toBe(1);
  await expect(page.getByRole("banner")).toHaveCount(2);
});

test("gap-12 covers the Phase 0 organisation routes", () => {
  expect(ROUTES.length).toBeGreaterThanOrEqual(5);
});

for (const route of ROUTES) {
  test(`gap-12: ${route} has no banner in the work area`, async ({ page }) => {
    await page.goto(route);
    const main = page.getByRole("main");
    await expect(main.getByRole("heading", { level: 1 })).toBeVisible();

    await expect(page.getByRole("banner")).toHaveCount(1);
    await expect(
      page.getByRole("banner").getByRole("button", { name: "Notifications" }),
    ).toBeVisible();

    expect(await page.locator(PROMO_SELECTOR).count()).toBe(0);

    const mainBox = await main.boundingBox();
    const headingBox = await main.getByRole("heading", { level: 1 }).boundingBox();
    expect(mainBox).not.toBeNull();
    expect(headingBox).not.toBeNull();
    expect(headingBox!.y - mainBox!.y).toBeLessThan(200);
    expect(headingBox!.y + headingBox!.height).toBeLessThan(800);
  });
}
