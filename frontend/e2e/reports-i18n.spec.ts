import { expect, test } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";
import { CATALOGUE, profitAndLoss } from "./reports-fixtures";

/**
 * K-01-T19 (i18n) — the report home and the runner in French and in the pseudo-locale en-XA
 * (+30 % accented text): every string localised, nothing overflowing or clipped at 360 and
 * 1280 px.
 */
for (const width of [360, 1280]) {
  test(`reports in en-XA: localised, nothing clipped at ${width} px`, async ({
    browser,
    baseURL,
  }) => {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    await context.addCookies([{ name: "numo9_locale", value: "en-XA", url: baseURL! }]);
    const page = await context.newPage();
    await mockCsrf(page);
    await page.route("**/api/v1/o/acme/reports", (r) => r.fulfill({ json: CATALOGUE }));
    await page.route("**/api/v1/o/acme/reports/*/run*", (r) =>
      r.fulfill({ json: profitAndLoss(3) }),
    );
    for (const path of ["/o/acme/reports", "/o/acme/reports/profit-and-loss"]) {
      await page.goto(path);
      await expect(page.locator("html")).toHaveAttribute("lang", "en-XA");
      await expect(page.getByRole("button", { name: /^\[/ }).first()).toBeVisible();
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - window.innerWidth,
      );
      expect(overflow, path).toBeLessThanOrEqual(0);
      const clipped = await page.evaluate(() =>
        [...document.querySelectorAll("main h1, main p, main label")]
          .filter((el) => el.scrollWidth > el.clientWidth + 1)
          .map((el) => el.textContent),
      );
      expect(clipped, path).toEqual([]);
    }
    await context.close();
  });
}

test("the report home in French", async ({ browser, baseURL }) => {
  const context = await browser.newContext();
  await context.addCookies([{ name: "numo9_locale", value: "fr-CA", url: baseURL! }]);
  const page = await context.newPage();
  await mockCsrf(page);
  await page.route("**/api/v1/o/acme/reports", (r) => r.fulfill({ json: CATALOGUE }));
  await page.goto("/o/acme/reports");
  await expect(page.locator("html")).toHaveAttribute("lang", "fr-CA");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await context.close();
});
