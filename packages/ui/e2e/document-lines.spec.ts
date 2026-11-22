import { expect, test, type Page } from "@playwright/test";

/**
 * D-01-T11 acceptance: a keyboard-only person fills 5 document lines (description, quantity,
 * unit price, account and tax code) without touching the mouse; Ctrl+D duplicates a line and
 * Ctrl+Backspace deletes one with an Undo toast. Axe runs on these stories in a11y.spec.ts.
 */
const EMPTY = "/iframe.html?id=data-linegrid--document-lines-empty&viewMode=story";

async function pick(page: Page, text: string) {
  await page.keyboard.type(text);
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
}

test("keyboard only: five lines", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(EMPTY);
  const grid = page.getByRole("grid", { name: "Invoice lines" });
  await expect(grid).toBeVisible();
  await page.getByRole("textbox", { name: "Description, line 1" }).focus();

  for (let n = 1; n <= 5; n += 1) {
    await expect(page.getByRole("textbox", { name: `Description, line ${n}` })).toBeFocused();
    await page.keyboard.type(`Service ${n}`);
    await page.keyboard.press("Tab");
    await page.keyboard.press("Control+a");
    await page.keyboard.type(String(n));
    await page.keyboard.press("Tab");
    await page.keyboard.type("100");
    await page.keyboard.press("Tab");
    await pick(page, "retail");
    await page.keyboard.press("Tab");
    await pick(page, "Ontario");
    if (n < 5) {
      // Enter on the last line adds a line in the same column; Shift+Tab back to Description.
      await page.keyboard.press("Enter");
      for (let back = 0; back < 4; back += 1) await page.keyboard.press("Shift+Tab");
    }
  }

  for (let n = 1; n <= 5; n += 1) {
    await expect(page.getByRole("textbox", { name: `Description, line ${n}` })).toHaveValue(
      `Service ${n}`,
    );
    await expect(page.getByRole("status", { name: `Amount, line ${n}`, exact: true })).toHaveText(
      `$${n * 100}.00`,
    );
    await expect(page.getByRole("status", { name: `Tax amount, line ${n}` })).toHaveText(
      `$${n * 13}.00`,
    );
  }
  // 1 500.00 + HST 195.00 in the totals row.
  await expect(page.locator("tr[data-totals]")).toContainText("$1,500.00");
  await expect(page.locator("tr[data-totals]")).toContainText("$195.00");
});

test("Ctrl+D duplicates, Ctrl+Backspace deletes with Undo", async ({ page }) => {
  await page.goto("/iframe.html?id=data-linegrid--document-lines-story&viewMode=story");
  await page.getByRole("textbox", { name: "Description, line 2" }).focus();
  await page.keyboard.press("Control+d");
  await expect(page.getByRole("textbox", { name: "Description, line 3" })).toHaveValue("Hardware");
  await expect(page.getByRole("textbox", { name: "Description, line 3" })).toBeFocused();
  await page.keyboard.press("Control+Backspace");
  await expect(page.getByRole("textbox", { name: "Description, line 3" })).toHaveCount(0);
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByRole("textbox", { name: "Description, line 3" })).toHaveValue("Hardware");
});

test("gap-07: a sales line offers no expense accounts and no purchase codes", async ({ page }) => {
  await page.goto("/iframe.html?id=data-linegrid--document-lines-story&viewMode=story");
  const account = page.getByRole("combobox", { name: "Account, line 1" });
  await account.click();
  await account.fill("");
  const accounts = page.getByRole("option");
  await expect(accounts.filter({ hasText: "Sales — retail" })).toHaveCount(1);
  await expect(accounts.filter({ hasText: "Office supplies" })).toHaveCount(0);
  await expect(accounts.filter({ hasText: "Fuel" })).toHaveCount(0);
  await page.keyboard.press("Escape");
  const tax = page.getByRole("combobox", { name: "Tax code, line 1" });
  await tax.click();
  await tax.fill("");
  const codes = page.getByRole("option");
  await expect(codes.filter({ hasText: "on sales" }).first()).toBeVisible();
  await expect(codes.filter({ hasText: "on purchases" })).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Why this tax code, line 1" }),
  ).toHaveAccessibleDescription("Ontario customer → HST 13 %");
});
