import { expect, test } from "@playwright/test";

import { expectAccessible } from "./auth-helpers";
import { CUSTOMER, ORG, TEMPLATE, mockRecurringInvoices } from "./recurring-invoices-fixtures";

/**
 * D-04-T08 — the recurring invoice template editor: a monthly template in under 2 minutes (name,
 * customer, a line on the same grid as the invoice editor, the schedule panel's next dates, the
 * mode, Save). Server side: backend/tests/test_recurring_invoices_api.py.
 */
test.use({ viewport: { width: 1440, height: 900 } });

test("a monthly template in under 2 minutes", async ({ page }) => {
  const started = Date.now();
  const state = await mockRecurringInvoices(page);
  await page.goto(`/o/${ORG}/sales/recurring-invoices/new`);
  const form = page.getByRole("form", { name: "New recurring invoice" });
  await expect(form.getByRole("option", { name: "Maple Leaf Supply Ltd." })).toBeAttached();
  await form.getByRole("textbox", { name: /^Name/ }).fill("Monthly bookkeeping");
  await form.getByRole("combobox", { name: "Customer" }).selectOption(CUSTOMER);
  await page.getByRole("textbox", { name: "Description, line 1" }).fill("Bookkeeping {{month}}");
  await page.getByRole("textbox", { name: "Unit price, line 1" }).fill("300");
  await expect(page.locator("[data-schedule-panel] [data-date]")).toHaveCount(6);
  await page
    .getByRole("radio", { name: /^Approve\b/ })
    .first()
    .check();
  await expectAccessible(page);
  await form.getByRole("button", { name: "Save" }).click();
  await expect(page).toHaveURL(new RegExp(`/sales/recurring-invoices/${TEMPLATE}$`));
  expect(Date.now() - started).toBeLessThan(120_000);
  expect(state.posts[0]).toMatchObject({
    path: "POST ",
    body: { name: "Monthly bookkeeping", rrule: "FREQ=MONTHLY;INTERVAL=1", mode: "approve" },
  });
});

test("the editor uses the invoice editor's grid", async ({ page }) => {
  await mockRecurringInvoices(page);
  await page.goto(`/o/${ORG}/sales/recurring-invoices/${TEMPLATE}`);
  await expect(
    page.getByRole("heading", { name: "Recurring invoice Monthly bookkeeping" }),
  ).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Description, line 1" })).toHaveValue(
    "Bookkeeping — {{month}}",
  );
  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByRole("button", { name: "Resume" })).toBeVisible();
});
