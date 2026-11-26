import { expect, test } from "@playwright/test";

import { expectAccessible } from "./auth-helpers";
import { ORG, RUNS, TEMPLATE, mockRecurringInvoices, row } from "./recurring-invoices-fixtures";

/**
 * D-04-T10 — the recurring invoices list (next run, last run, status) and the generated history
 * tab: the counts match — the list's "1 invoice, 1 skipped" is the history's rows.
 * Server side: backend/tests/test_recurring_invoices_api.py.
 */
test.use({ viewport: { width: 1440, height: 900 } });

test("the list shows next and last run and status; the history counts match", async ({ page }) => {
  await mockRecurringInvoices(page);
  await page.goto(`/o/${ORG}/sales/recurring-invoices`);
  const line = page.locator(`[data-template="${TEMPLATE}"]`);
  await expect(line.getByRole("link", { name: row().name })).toBeVisible();
  await expect(line.locator("[data-next-run]")).toHaveText("15 Jul 2026");
  await expect(line.locator("[data-last-run]")).toHaveText("15 Jun 2026");
  await expect(line.getByText("Active")).toBeVisible();
  await expect(line.locator("[data-generated]")).toHaveText("1 invoice, 1 skipped");
  await expect(page.getByRole("tab", { name: "All (1)" })).toBeVisible();
  await expectAccessible(page);

  await line.getByRole("link", { name: row().name }).click();
  await page.getByRole("tab", { name: "Generated invoices" }).click();
  const history = page.locator("[data-history]");
  await expect(history.locator("[data-history-counts]")).toHaveText("1 invoice, 1 skipped");
  await expect(history.locator("[data-run]")).toHaveCount(RUNS.length);
  await expect(history.locator('[data-run="created"]')).toHaveCount(1);
  await expect(history.locator('[data-run="skipped"]')).toHaveCount(1);
  await expect(history.getByRole("link", { name: "INV-0007" })).toBeVisible();
});
