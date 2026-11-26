import { expect, test, type Page } from "@playwright/test";

import { expectAccessible } from "./auth-helpers";
import { INVOICE, ORG, mockInvoiceEditor, preview, savedInvoice } from "./invoices-fixtures";

/**
 * D-03a-T14 — the invoice action bar's state matrix, the posting preview drawer (the preview
 * matches the posted journal) and the period ribbon. Server side: the posted journal is the
 * preview's own lines (backend/tests/test_invoices_api.py::test_preview_approve_void_copy).
 */
test.use({ viewport: { width: 1440, height: 900 } });

async function journalRows(page: Page) {
  const drawer = page.getByRole("dialog");
  await expect(drawer.locator("[data-posting-preview]")).toBeVisible();
  const rows = await drawer.locator("tbody tr").allInnerTexts();
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  return rows;
}

test("the posting preview matches the posted journal", async ({ page }) => {
  const state = await mockInvoiceEditor(page);
  await page.goto(`/o/${ORG}/sales/invoices/${INVOICE}`);
  const bar = page.getByRole("toolbar", { name: "Invoice actions" });
  await expect(bar).toHaveAttribute("data-invoice-actions", "save approve preview delete");
  await expect(page.getByRole("group", { name: "Period" })).toHaveAttribute(
    "data-period-ribbon",
    "open",
  );

  await bar.getByRole("button", { name: "Preview posting" }).click();
  await expect(page.getByRole("dialog", { name: "What approval posts" })).toBeVisible();
  await expectAccessible(page);
  const before = await journalRows(page);
  expect(before).toHaveLength(2);

  await bar.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("Invoice INV-0001 approved and posted.")).toBeVisible();
  expect(state.posts.map((p) => p.path)).toEqual([`PATCH /${INVOICE}`, `POST /${INVOICE}/approve`]);
  await expect(bar).toHaveAttribute(
    "data-invoice-actions",
    "email pdf copy copy_quote void preview",
  );
  await bar.getByRole("button", { name: "Preview posting" }).click();
  await expect(page.getByRole("dialog", { name: "Posted journal" })).toBeVisible();
  expect(await journalRows(page)).toEqual(before);
});

test("void asks for the date and reason; the ribbon shows a filed period", async ({ page }) => {
  const state = await mockInvoiceEditor(
    page,
    savedInvoice({ status: "approved", status_label: "Approved", number: "INV-0001" }),
  );
  state.preview = preview({
    period: {
      date: "2026-06-15",
      ar_lock: "2026-03-31",
      locked: false,
      lock: null,
      tax_period: {
        start: "2026-04-01",
        end: "2026-06-30",
        status: "filed",
        filed: true,
        due_date: "2026-07-31",
      },
    },
  });
  await page.goto(`/o/${ORG}/sales/invoices/${INVOICE}`);
  const ribbon = page.getByRole("group", { name: "Period" });
  await expect(ribbon).toHaveAttribute("data-period-ribbon", "blocked");
  await expect(ribbon).toContainText("GST/HST period 1 Apr 2026 – 30 Jun 2026 is filed");
  await page.getByRole("button", { name: "Void" }).click();
  const dialog = page.getByRole("dialog", { name: "Void invoice INV-0001?" });
  await dialog.getByLabel("Void date").fill("2026-07-02");
  await dialog.getByRole("textbox", { name: "Reason" }).fill("Wrong customer");
  await dialog.getByRole("button", { name: "Void" }).click();
  await expect(page.getByText("Invoice voided.")).toBeVisible();
  expect(state.posts.at(-1)).toEqual({
    path: `POST /${INVOICE}/void`,
    body: { date: "2026-07-02", reason: "Wrong customer" },
  });
  await expect(page.getByRole("toolbar", { name: "Invoice actions" })).toHaveAttribute(
    "data-invoice-actions",
    "pdf copy preview",
  );
});
