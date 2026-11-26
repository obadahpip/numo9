import { expect, test } from "@playwright/test";

import { expectAccessible } from "./auth-helpers";
import { BILL, mockReferenceData, ORG, savedOrder } from "./purchase-orders-fixtures";

/**
 * E-01-T13 — PO list: tab counts equal the server's counts per status (Partially received and
 * Received among them, All = their sum); a tab lists its POs; "Create bill" opens the draft bill.
 */
const COUNTS = {
  draft: 2,
  awaiting_approval: 1,
  approved: 0,
  partially_received: 3,
  received: 1,
  billed: 4,
  closed: 0,
  cancelled: 1,
};
const row = (over: Record<string, unknown>) => {
  const all = savedOrder(over);
  return {
    id: all.id,
    number: all.number,
    status: all.status,
    status_label: all.status_label,
    supplier: all.supplier,
    reference: "",
    date: all.date,
    delivery_date: all.delivery_date,
    total: all.total,
    url: all.url,
  };
};

test("tab counts are correct and Create bill opens the bill", async ({ page }) => {
  await mockReferenceData(page);
  const partial = row({ number: "PO-0007", status: "partially_received" });
  await page.route(`**/api/v1/o/${ORG}/purchase-orders*`, (r) => {
    const status = new URL(r.request().url()).searchParams.get("status");
    return r.fulfill({
      json: {
        count: 12,
        page: 1,
        pages: 1,
        counts: COUNTS,
        results: status === "partially_received" ? [partial] : [partial, row({})],
      },
    });
  });
  await page.route(`**/api/v1/o/${ORG}/bills/from-po`, (r) =>
    r.fulfill({ status: 201, json: { id: BILL } }),
  );
  await page.route(`**/api/v1/o/${ORG}/bills/${BILL}*`, (r) =>
    r.fulfill({ status: 404, json: {} }),
  );
  await page.goto(`/o/${ORG}/purchases/orders`);
  const tabs = page.getByRole("tablist", { name: "Purchase orders by status" });
  await expect(tabs.getByRole("tab", { name: /^All/ })).toContainText("12");
  await expect(tabs.getByRole("tab", { name: /Partially received/ })).toContainText("3");
  await expect(tabs.getByRole("tab", { name: /^Received/ })).toContainText("1");
  await expect(tabs.getByRole("tab", { name: /Billed/ })).toContainText("4");
  await expectAccessible(page);
  await tabs.getByRole("tab", { name: /Partially received/ }).click();
  await expect(page.getByRole("row")).toHaveCount(2);
  await page.getByRole("button", { name: "Create bill from PO-0007" }).click();
  await expect(page).toHaveURL(new RegExp(`/purchases/bills/${BILL}$`));
});
