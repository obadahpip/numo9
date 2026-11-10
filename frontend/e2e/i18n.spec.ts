import { expect, test } from "@playwright/test";

/**
 * A-10-T13: locale from the `numo9_locale` cookie or Accept-Language (no locale in the URL), and
 * the pseudo-locale en-XA (+30 % accented text) without clipped or overflowing layouts at 360 and
 * 1280 px (Phase 0 plan §3.6).
 */
const PAGE = "/o/acme/settings/lock-dates";

test("default locale is en-CA", async ({ page }) => {
  await page.goto(PAGE);
  await expect(page.locator("html")).toHaveAttribute("lang", "en-CA");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Settings: Lock dates");
});

test("French from Accept-Language or the locale cookie", async ({ browser, baseURL }) => {
  // The browser language (Accept-Language: fr-FR).
  const viaHeader = await browser.newContext({ locale: "fr-FR" });
  const page = await viaHeader.newPage();
  await page.goto(PAGE);
  await expect(page.locator("html")).toHaveAttribute("lang", "fr-CA");
  await viaHeader.close();

  const viaCookie = await browser.newContext();
  await viaCookie.addCookies([{ name: "numo9_locale", value: "fr-CA", url: baseURL! }]);
  const page2 = await viaCookie.newPage();
  await page2.goto(PAGE);
  await expect(page2.locator("html")).toHaveAttribute("lang", "fr-CA");
  await viaCookie.close();
});

for (const width of [360, 1280]) {
  test(`pseudo-locale en-XA: every string localised, nothing clipped at ${width} px`, async ({
    browser,
    baseURL,
  }) => {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    await context.addCookies([{ name: "numo9_locale", value: "en-XA", url: baseURL! }]);
    const page = await context.newPage();
    await page.goto(PAGE);
    await expect(page.locator("html")).toHaveAttribute("lang", "en-XA");

    const heading = page.getByRole("heading", { level: 1 });
    await expect(heading).toHaveText(/^\[Š.*~+\]$/);
    await expect(page.getByRole("link", { name: /^\[Šķîþ ţö çöñţéñţ/ })).toBeAttached();

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);

    // Headings and body text wrap instead of being cut off.
    const clipped = await page.evaluate(() =>
      [...document.querySelectorAll("main h1, main p")]
        .filter((el) => el.scrollWidth > el.clientWidth + 1)
        .map((el) => el.textContent),
    );
    expect(clipped).toEqual([]);
    await context.close();
  });
}
