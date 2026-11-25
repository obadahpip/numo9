import { expect, test } from "@playwright/test";

import { BILL, mockBillEditor, savedBill } from "./bills-fixtures";

/**
 * G-03b-T12 — a document dated after a GST/HST stop that uses its codes shows the server's
 * `REGISTRATION_STOPPED` warning inline in the editor (here the bill editor, which shares the
 * live calculation with the invoice editor); it doesn't block. Server side:
 * backend/tests/test_documents_stop_warning.py.
 */
const ORG = "acme";
const MESSAGE =
  "GST/HST 123456782 RT 0001 wasn't registered on 2026-07-15 (filing stopped after 2026-06-30): this document shouldn't use its tax codes.";

test("warning visible on a 15 Jul document", async ({ page }) => {
  await mockBillEditor(page);
  await page.route(`**/api/v1/o/${ORG}/bills/${BILL}`, (r) =>
    r.fulfill({ json: savedBill({ date: "2026-07-15" }) }),
  );
  let asked = 0;
  await page.route(`**/api/v1/o/${ORG}/documents/purchases/calculate`, (r) => {
    asked += 1;
    return r.fulfill({
      json: {
        kind: "bill",
        tax_mode: "exclusive",
        lines: [
          {
            gross: "450.00",
            line_discount: "0.00",
            net: "450.00",
            discount_share: "0.00",
            taxable: "450.00",
            exclusive: "450.00",
            tax: "58.50",
            taxes: [{ key: "hst_on", rate: "13", amount: "58.50" }],
          },
        ],
        subtotal: "450.00",
        discount_total: "0.00",
        tax_total: "58.50",
        total: "508.50",
        net_total: "450.00",
        tax_included: false,
        tax_by_component: [{ key: "hst_on", name: "HST", amount: "58.50" }],
        problems: [],
        warnings: [{ code: "REGISTRATION_STOPPED", message: MESSAGE }],
      },
    });
  });
  await page.goto(`/o/${ORG}/purchases/bills/${BILL}`);
  const warning = page.locator('[data-warning="REGISTRATION_STOPPED"]');
  await expect(warning).toHaveText(MESSAGE);
  expect(asked).toBeGreaterThan(0);
  await expect(page.getByRole("region", { name: "Review before saving" })).toBeVisible();
});
