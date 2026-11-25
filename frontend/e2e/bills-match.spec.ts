import { expect, test } from "@playwright/test";

import { expectAccessible } from "./auth-helpers";
import { BILL, mockBillEditor, savedBill } from "./bills-fixtures";

/**
 * E-02-T13 — the match panel colours each PO line and a bill that doesn't match is approved only
 * "with variance", by an approver (the rule and the 403 for others: backend tests
 * test_bill_from_po.py and test_bill_api.py).
 */
const ORG = "acme";
const MATCH = [
  {
    line: "l1",
    po_line: "p1",
    po: "PO-0007",
    description: "Tiles",
    ordered: "10.0000",
    received: "10.0000",
    billed_elsewhere: "0.0000",
    quantity: "12.0000",
    po_price: "45.0000",
    price: "45.0000",
    quantity_over: "2.0000",
    price_difference_pct: "0.00",
    status: "red",
  },
  {
    line: "l2",
    po_line: "p2",
    po: "PO-0007",
    description: "Grout",
    ordered: "4.0000",
    received: "4.0000",
    billed_elsewhere: "0.0000",
    quantity: "4.0000",
    po_price: "80.0000",
    price: "82.0000",
    quantity_over: "0.0000",
    price_difference_pct: "2.50",
    status: "amber",
  },
];

test("variance needs Approve with variance", async ({ page }) => {
  await mockBillEditor(page);
  const approvals: unknown[] = [];
  await page.route(`**/api/v1/o/${ORG}/bills/${BILL}/preview`, (r) =>
    r.fulfill({
      json: {
        journal: { lines: [], complete: true },
        itc: [],
        routing: { rule: null, role: null, role_name: null, explanation: "" },
        duplicates: [],
        match: MATCH,
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/bills/${BILL}/approve`, async (r) => {
    const body = r.request().postDataJSON() as { with_variance: boolean };
    approvals.push(body);
    if (!body.with_variance) {
      await r.fulfill({
        status: 400,
        json: {
          code: "purchases.bill.variance",
          detail:
            "The bill doesn't match its purchase order and receipts: review the match panel and approve with variance.",
        },
      });
      return;
    }
    await r.fulfill({
      json: savedBill({
        status: "awaiting_payment",
        status_label: "Awaiting payment",
        number: "BILL-0003",
      }),
    });
  });
  await page.route(`**/api/v1/o/${ORG}/bills/${BILL}`, (r) => r.fulfill({ json: savedBill() }));
  await page.goto(`/o/${ORG}/purchases/bills/${BILL}`);
  const panel = page.getByRole("region", { name: "Match with purchase order PO-0007" });
  await expect(panel.locator('[data-match="red"]')).toContainText("Doesn't match");
  await expect(panel.locator('[data-match="red"]')).toContainText("2 more than received");
  await expect(panel.locator('[data-match="amber"]')).toContainText("price 2.5 % off");
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.locator('[data-refusal="purchases.bill.variance"]')).toContainText(
    "approve with variance",
  );
  await expectAccessible(page);
  await page.getByRole("button", { name: "Approve with variance" }).click();
  await expect(page.getByText("BILL-0003 is approved and awaiting payment.")).toBeVisible();
  expect(approvals).toEqual([{ with_variance: false }, { with_variance: true }]);
});
