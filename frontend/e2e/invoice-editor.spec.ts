import { expect, test } from "@playwright/test";

import { expectAccessible } from "./auth-helpers";
import { CUSTOMER, INVOICE, ORG, REVENUE, mockInvoiceEditor } from "./invoices-fixtures";

/**
 * D-03a-T13 — the invoice editor: a first invoice in at most 5 clicks (customer, description,
 * price, save — the line starts on the revenue account); header, grid, totals and attachments.
 * Server side: backend/tests/test_invoices_api.py.
 */
test.use({ viewport: { width: 1440, height: 900 } });

test("a first invoice in at most 5 clicks", async ({ page }) => {
  const state = await mockInvoiceEditor(page);
  await page.goto(`/o/${ORG}/sales/invoices/new`);
  const form = page.getByRole("form", { name: "New invoice" });
  await expect(form.getByRole("option", { name: "Maple Leaf Supply Ltd." })).toBeAttached();
  let clicks = 0;
  const click = async (run: () => Promise<void>) => {
    clicks += 1;
    await run();
  };
  await click(() => form.getByRole("combobox", { name: "Customer" }).selectOption(CUSTOMER));
  await click(() => page.getByRole("textbox", { name: "Description, line 1" }).fill("Design"));
  await click(() => page.getByRole("textbox", { name: "Unit price, line 1" }).fill("250"));
  await page.keyboard.press("Tab");
  await expect(page.locator('[data-total="total"]')).toContainText("$250.00");
  await expectAccessible(page);
  await click(() => form.getByRole("button", { name: "Save draft" }).click());
  await expect(page.getByText("Draft saved.")).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/sales/invoices/${INVOICE}$`));
  expect(clicks).toBeLessThanOrEqual(5);
  expect(state.posts[0]).toMatchObject({
    path: "POST ",
    body: { customer: CUSTOMER, lines: [{ description: "Design", account: REVENUE }] },
  });
});

test("a saved draft opens with its header, lines and totals", async ({ page }) => {
  await mockInvoiceEditor(page);
  await page.goto(`/o/${ORG}/sales/invoices/${INVOICE}`);
  await expect(page.getByRole("heading", { name: "Draft invoice" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Description, line 1" })).toHaveValue(
    "Design consultation",
  );
  await expect(page.getByRole("heading", { name: "Attachments" })).toBeVisible();
  await expect(page.getByText("No files attached.")).toBeVisible();
  await expectAccessible(page);
});
