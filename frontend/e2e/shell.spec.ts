import { expect, test, type Page } from "@playwright/test";

/**
 * A-10-T05 acceptance: the application shell works from 360 px to 1440 px (Phase 0 UX principle 17:
 * breakpoints 360 / 768 / 1024 / 1440, no horizontal scroll, 44 px touch targets).
 */
const VIEWPORTS = [360, 768, 1024, 1440] as const;
const DESKTOP = 1024;

async function horizontalOverflow(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
}

for (const width of VIEWPORTS) {
  test.describe(`app shell at ${width} px`, () => {
    test.use({ viewport: { width, height: 900 } });

    test("shows the shell regions without horizontal scroll", async ({ page }) => {
      await page.goto("/o/acme/accounting/journals");

      const banner = page.getByRole("banner");
      await expect(banner).toBeVisible();
      await expect(banner.getByRole("link", { name: "Numo9 home" })).toBeVisible();
      await expect(banner.getByText("acme", { exact: true })).toBeVisible();
      await expect(banner.getByRole("button", { name: "Notifications" })).toBeVisible();
      await expect(banner.getByRole("button", { name: "Account menu" })).toBeVisible();
      await expect(page.getByRole("navigation", { name: "Breadcrumbs" })).toBeVisible();
      await expect(page.getByRole("main").getByRole("heading", { level: 1 })).toHaveText(
        "Journals",
      );

      expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
    });

    test("navigation: top bar on desktop, drawer below 1024 px", async ({ page }) => {
      await page.goto("/o/acme/accounting/journals");
      const menuButton = page.getByRole("button", { name: "Open navigation" });
      const topNav = page.getByRole("banner").getByRole("navigation", { name: "Main" });

      if (width >= DESKTOP) {
        await expect(menuButton).toBeHidden();
        await expect(topNav.getByRole("link", { name: "Accounting" })).toBeVisible();
        await expect(topNav.getByRole("link", { name: "Accounting" })).toHaveAttribute(
          "aria-current",
          "page",
        );
        return;
      }

      await expect(topNav).toBeHidden();
      await menuButton.click();
      const drawer = page.getByRole("dialog", { name: "Navigation" });
      await expect(drawer).toBeVisible();
      await expect(drawer.getByRole("link", { name: "Accounting" })).toHaveAttribute(
        "aria-current",
        "page",
      );
      expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);

      await page.keyboard.press("Escape");
      await expect(drawer).toBeHidden();
      await expect(menuButton).toBeFocused();

      await menuButton.click();
      await page.getByRole("dialog").getByRole("link", { name: "Contacts" }).click();
      await expect(page).toHaveURL(/\/o\/acme\/contacts$/);
      await expect(page.getByRole("dialog")).toBeHidden();
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("Contacts");
    });

    test("top-bar controls are at least 44 × 44 px", async ({ page }) => {
      await page.goto("/o/acme/home");
      const controls = page.getByRole("banner").locator("a:visible, button:visible");
      const count = await controls.count();
      expect(count).toBeGreaterThanOrEqual(3);
      for (let i = 0; i < count; i++) {
        const box = await controls.nth(i).boundingBox();
        expect(box, await controls.nth(i).innerText()).not.toBeNull();
        expect(box!.height).toBeGreaterThanOrEqual(44);
        if (width < DESKTOP) expect(box!.width).toBeGreaterThanOrEqual(44);
      }
    });

    test("a 63-character organisation slug truncates instead of overflowing", async ({ page }) => {
      const slug = `a${"b".repeat(61)}c`;
      await page.goto(`/o/${slug}/settings/general`);
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("Settings: General");
      expect(await horizontalOverflow(page)).toBeLessThanOrEqual(0);
      const user = await page.getByRole("button", { name: "Account menu" }).boundingBox();
      expect(user!.x + user!.width).toBeLessThanOrEqual(width);
    });
  });
}

test.describe("keyboard", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("skip link moves focus to the main content", async ({ page }) => {
    await page.goto("/o/acme/home");
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Skip to content" });
    await expect(skip).toBeFocused();
    await expect(skip).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("main")).toBeFocused();
  });

  test("user menu opens with the keyboard and closes with Escape", async ({ page }) => {
    await page.goto("/o/acme/home");
    const button = page.getByRole("button", { name: "Account menu" });
    await button.focus();
    await page.keyboard.press("Enter");
    const item = page.getByRole("menuitem", { name: "Organisation settings" });
    await expect(item).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("menu")).toBeHidden();
    await expect(button).toBeFocused();
  });
});
