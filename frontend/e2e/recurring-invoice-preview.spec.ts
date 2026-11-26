import { expect, test } from "@playwright/test";

import { expectAccessible } from "./auth-helpers";
import {
  INVOICE,
  NEXT_INVOICE,
  ORG,
  TEMPLATE,
  mockRecurringInvoices,
} from "./recurring-invoices-fixtures";

/**
 * D-04-T09 — "Preview next invoice": the preview equals the generated invoice (the server builds
 * it with the generator's own code; backend/tests/test_recurring_invoices_api.py checks the
 * equality field by field against the invoice the tick then creates).
 */
test.use({ viewport: { width: 1440, height: 900 } });

test("the preview shows the next invoice as it will be generated", async ({ page }) => {
  await mockRecurringInvoices(page);
  await page.goto(`/o/${ORG}/sales/recurring-invoices/${TEMPLATE}`);
  const preview = page.locator("[data-recurring-preview]");
  await expect(preview.getByRole("heading", { name: "Preview next invoice" })).toBeVisible();
  await expect(preview.locator("[data-preview-reference]")).toHaveText(NEXT_INVOICE.reference);
  await expect(preview.getByText("Bookkeeping — July")).toBeVisible();
  await expect(preview.locator("[data-preview-total]")).toHaveText("$300.00");
  await expectAccessible(page);

  // The generated invoice (history → invoice) carries the same reference, lines and total.
  const generated = await page.request.get(`/api/v1/o/${ORG}/invoices/${INVOICE}`);
  const invoice = (await generated.json()) as typeof NEXT_INVOICE;
  expect(invoice.reference).toBe(NEXT_INVOICE.reference);
  expect(invoice.total).toBe(NEXT_INVOICE.total);
  expect(invoice.lines.map((l) => l.description)).toEqual(["Bookkeeping — July"]);
});
