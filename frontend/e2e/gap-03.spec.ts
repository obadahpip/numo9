import { expect, test, type Page } from "@playwright/test";

import { auditLabels, blocking, describeFindings, runAxe } from "../../packages/ui/e2e/a11y";

/**
 * gap-03 (A-05-T10): settings are deep-linked per section and each module's gear opens its own
 * section — Xero sends every module's "Settings" link to one generic page (teardown §0).
 *
 * - every settings section has its own URL `/o/:org/settings/<section>` that renders (200) with
 *   the settings navigation, where every link is that section's own URL and the current section
 *   is marked;
 * - following any link in the navigation lands on that section (no redirect, no generic page);
 * - each module's gear links to its own settings section and opens it.
 */
const SECTIONS = [
  ["general", "General"],
  ["registrations", "Tax registrations"],
  ["lock-dates", "Lock dates"],
  ["users-roles", "Users and roles"],
  ["email-domain", "Email domain"],
  ["subscription", "Subscription"],
  ["numbering", "Numbering"],
  ["custom-fields", "Custom fields"],
  ["audit-log", "Audit log"],
  ["package-features", "Package and features"],
] as const;

const GEARS = [
  ["contacts", "Contacts settings", "custom-fields"],
  ["accounting/chart-of-accounts", "Chart of accounts settings", "general"],
  ["accounting/journals", "Journals settings", "lock-dates"],
] as const;

const ORG = "acme";

function settingsNav(page: Page) {
  return page.getByRole("navigation", { name: "Settings sections" });
}

test.describe("gap-03: every settings section is deep-linked", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  for (const [section, name] of SECTIONS) {
    test(`/o/${ORG}/settings/${section} renders its own section`, async ({ page }) => {
      const response = await page.goto(`/o/${ORG}/settings/${section}`);
      expect(response?.status()).toBe(200);
      expect(new URL(page.url()).pathname).toBe(`/o/${ORG}/settings/${section}`);

      const nav = settingsNav(page);
      await expect(nav).toBeVisible();
      const links = nav.getByRole("link");
      await expect(links).toHaveCount(SECTIONS.length);
      for (const [other, otherName] of SECTIONS) {
        await expect(nav.getByRole("link", { name: otherName, exact: true })).toHaveAttribute(
          "href",
          `/o/${ORG}/settings/${other}`,
        );
      }
      await expect(nav.locator('[aria-current="page"]')).toHaveText(name);

      const trail = page.getByRole("navigation", { name: "Breadcrumbs" });
      await expect(trail.getByRole("link", { name: "Settings" })).toHaveAttribute(
        "href",
        `/o/${ORG}/settings/general`,
      );
      await expect(trail.locator('[aria-current="page"]')).toHaveText(name);
    });
  }

  test("following each navigation link lands on that section", async ({ page }) => {
    await page.goto(`/o/${ORG}/settings/general`);
    for (const [section, name] of SECTIONS) {
      await settingsNav(page).getByRole("link", { name, exact: true }).click();
      await expect(page).toHaveURL(new RegExp(`/o/${ORG}/settings/${section}(\\?.*)?$`));
      await expect(settingsNav(page).locator('[aria-current="page"]')).toHaveText(name);
    }
  });

  test("a settings page has no serious a11y finding and no sideways scroll at 360 px", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await page.goto(`/o/${ORG}/settings/lock-dates`);
    await expect(settingsNav(page)).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
    const findings = blocking(await runAxe(page));
    expect(findings, describeFindings(findings)).toEqual([]);
    expect(await auditLabels(page)).toEqual([]);
  });
});

test.describe("gap-03: each module's gear opens its own settings section", () => {
  test.use({ viewport: { width: 1280, height: 900 } });

  for (const [module, gear, section] of GEARS) {
    test(`${module} → settings/${section}`, async ({ page }) => {
      await page.goto(`/o/${ORG}/${module}`);
      const link = page.getByRole("link", { name: gear });
      await expect(link).toHaveAttribute("href", `/o/${ORG}/settings/${section}`);
      await link.click();
      await expect(page).toHaveURL(`/o/${ORG}/settings/${section}`);
      const name = SECTIONS.find(([key]) => key === section)?.[1] ?? "";
      await expect(settingsNav(page).locator('[aria-current="page"]')).toHaveText(name);
    });
  }

  test("the gears don't all go to one generic page", async ({ page }) => {
    const targets = new Set<string>();
    for (const [module, gear] of GEARS) {
      await page.goto(`/o/${ORG}/${module}`);
      targets.add((await page.getByRole("link", { name: gear }).getAttribute("href")) ?? "");
    }
    expect(targets.size).toBe(GEARS.length);
    expect([...targets]).not.toContain(`/o/${ORG}/settings`);
  });
});
