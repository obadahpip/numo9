import { expect, test } from "@playwright/test";

import { expectAccessible } from "./auth-helpers";
import { approvedOrder, LINE_1, mockReferenceData, ORG, PO } from "./purchase-orders-fixtures";

/**
 * E-01-T12 — receive screen: a partial receipt (6 of 10 tiles) keyed with Enter-to-next, then
 * 4 outstanding and Partially received; an over-receipt warns and is confirmed. Axe on the
 * screen. The receipt rules are tested in backend/tests/test_goods_receipt.py and the API in
 * test_purchase_order_api.py.
 */
test("partial receipt flow", async ({ page }) => {
  await mockReferenceData(page);
  let current: Record<string, unknown> = approvedOrder();
  const posted: Record<string, unknown>[] = [];
  await page.route(`**/api/v1/o/${ORG}/purchase-orders/${PO}`, (r) => r.fulfill({ json: current }));
  await page.route(`**/api/v1/o/${ORG}/receipts`, async (r) => {
    posted.push(r.request().postDataJSON() as Record<string, unknown>);
    const base = approvedOrder();
    const lines = (base.lines as Record<string, unknown>[]).map((line) =>
      line.id === LINE_1 ? { ...line, quantity_received: "6.0000", outstanding: "4.0000" } : line,
    );
    current = { ...base, status: "partially_received", status_label: "Partially received", lines };
    await r.fulfill({
      status: 201,
      json: { id: "r1", warnings: [], purchase_order_status: "partially_received" },
    });
  });
  await page.goto(`/o/${ORG}/purchases/orders/${PO}/receive`);
  await expect(page.getByRole("heading", { name: "Receive goods: PO-0001" })).toBeVisible();
  await expectAccessible(page);
  const tiles = page.getByRole("textbox", { name: "Receiving now: Tiles" });
  await tiles.fill("6");
  await tiles.press("Enter");
  await expect(page.getByRole("textbox", { name: "Receiving now: Grout" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByText("Receipt recorded. 8 still outstanding.")).toBeVisible();
  await expect(page.getByRole("row", { name: /Tiles/ })).toContainText("4");
  expect(posted[0]).toMatchObject({ lines: [{ po_line: LINE_1, quantity: "6" }] });
});

test("over-receipt warning is confirmed", async ({ page }) => {
  await mockReferenceData(page);
  await page.route(`**/api/v1/o/${ORG}/purchase-orders/${PO}`, (r) =>
    r.fulfill({ json: approvedOrder() }),
  );
  const posted: Record<string, unknown>[] = [];
  await page.route(`**/api/v1/o/${ORG}/receipts`, async (r) => {
    const body = r.request().postDataJSON() as Record<string, unknown>;
    posted.push(body);
    if (!body.confirm_over)
      return r.fulfill({
        status: 400,
        json: {
          code: "purchases.receipt.over_tolerance_confirm",
          detail: "This receives more than ordered: confirm to receive it anyway.",
          over: [{ line: "Tiles", ordered: "10.0000", received: "12.0000", allowed: "10.0000" }],
        },
      });
    return r.fulfill({
      status: 201,
      json: { id: "r1", warnings: [], purchase_order_status: "partially_received" },
    });
  });
  await page.goto(`/o/${ORG}/purchases/orders/${PO}/receive`);
  await page.getByRole("textbox", { name: "Receiving now: Tiles" }).fill("12");
  await expect(page.getByText("2 more than ordered")).toBeVisible();
  await page.getByRole("button", { name: "Record receipt" }).click();
  await expect(page.getByRole("alert")).toContainText("Tiles: 12 received of 10 ordered");
  await expectAccessible(page);
  await page.getByRole("button", { name: "Receive anyway" }).click();
  await expect(page.getByText(/Receipt recorded/)).toBeVisible();
  expect(posted.at(-1)).toMatchObject({ confirm_over: true });
});
