import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { entitlements, mockEntitlements } from "./entitlements-fixtures";

/**
 * F-01-T13 — banking quick-create and search: `N S` opens Spend money; the top bar "+" menu lists
 * Spend money, Receive money and Add bank account with their shortcuts; the palette finds the Petty
 * Cash account by "petty" (the search API itself: backend/tests/test_banking_search.py).
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const PETTY = "8c4d2e3f-0000-4000-8000-000000000003";

async function mockApi(page: Page) {
  await mockCsrf(page);
  await mockEntitlements(page, ORG, entitlements());
  await page.route(`**/api/v1/o/${ORG}/my-permissions`, (route) =>
    route.fulfill({
      json: { permissions: ["accounting.banking.transact", "accounting.banking.manage"] },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/search?*`, (route) =>
    route.fulfill({
      json: {
        query: "petty",
        records: [
          {
            type: "banking.bankaccount",
            id: PETTY,
            title: "Petty Cash",
            subtitle: "Cash / petty cash",
            code: "1010",
            amount: null,
            date: null,
            url: `/o/${ORG}/banking/${PETTY}`,
            match: "text",
            locked: false,
            reason: null,
          },
        ],
        settings: [],
        reports: [],
        navigation: [],
      },
    }),
  );
  // The screens behind the links: enough to land on them.
  await page.route(`**/api/v1/o/${ORG}/bank-accounts*`, (route) =>
    route.fulfill({ json: { results: [] } }),
  );
}

test.use({ viewport: { width: 1440, height: 900 } });

test("N S opens Spend money; the + menu shows the banking actions with shortcuts", async ({
  page,
}) => {
  await mockApi(page);
  await page.goto(`/o/${ORG}/settings/general`);
  await expect(page.getByRole("button", { name: "Create" })).toBeVisible();

  await page.getByRole("button", { name: "Create" }).click();
  const menu = page.getByRole("menu", { name: "Create" });
  await expect(menu.getByRole("menuitem", { name: /Spend money/ })).toContainText("N S");
  await expect(menu.getByRole("menuitem", { name: /Receive money/ })).toContainText("N R");
  await expect(menu.getByRole("menuitem", { name: /Add bank account/ })).toContainText("N A");
  await expectAccessible(page);
  await page.keyboard.press("Escape");
  await expect(menu).toHaveCount(0);

  await page.locator("body").click();
  await page.keyboard.press("n");
  await page.keyboard.press("s");
  await expect(page).toHaveURL(`/o/${ORG}/banking/spend`);
});

test("the palette finds the Petty Cash account by 'petty'", async ({ page }) => {
  await mockApi(page);
  await page.goto(`/o/${ORG}/settings/general`);
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: "Search" });
  await dialog.getByRole("combobox").fill("petty");
  const hit = dialog.getByRole("option", { name: /Petty Cash/ });
  await expect(hit).toBeVisible();
  await hit.click();
  await expect(page).toHaveURL(`/o/${ORG}/banking/${PETTY}`);
});
