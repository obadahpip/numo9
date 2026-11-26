import { expect, test } from "@playwright/test";

import { expectAccessible } from "./auth-helpers";
import { mockOrderEditor, ORG, PO, SUPPLIER } from "./purchase-orders-fixtures";

/**
 * E-01-T11 — PO editor: a purchase order is keyed and approved in under 90 seconds — supplier,
 * one line on the shared grid (purchase mode), the delivery block, the limit indicator, Approve.
 * The API side is tested in backend/tests/test_purchase_order_api.py.
 */
test("a purchase order is created in under 90 seconds", async ({ page }) => {
  test.setTimeout(90_000);
  const posted = await mockOrderEditor(page);
  const started = Date.now();
  await page.goto(`/o/${ORG}/purchases/orders/new`);
  const form = page.getByRole("form", { name: "New purchase order" });
  await form.getByRole("combobox", { name: "Supplier" }).selectOption(SUPPLIER);
  await page.getByRole("textbox", { name: "Description, line 1" }).fill("Tiles");
  await page.getByRole("textbox", { name: "Qty, line 1" }).fill("10");
  await page.getByRole("textbox", { name: "Unit cost, line 1" }).fill("25");
  await page.getByRole("combobox", { name: "Account, line 1" }).click();
  await page.getByRole("option", { name: /6100/ }).click();
  await form.getByRole("textbox", { name: "Deliver to" }).fill("12 King St W, Toronto ON");
  await form.getByRole("textbox", { name: "Attention" }).fill("Site office");
  await expect(page.getByRole("status", { name: "Approval limit" })).toContainText(
    "Within your approval limit",
  );
  await expectAccessible(page);
  await form.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("PO-0001 is approved. Send it to the supplier.")).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/purchases/orders/${PO}$`));
  expect(Date.now() - started).toBeLessThan(90_000);
  expect(posted[0]).toMatchObject({
    supplier: SUPPLIER,
    delivery_address: "12 King St W, Toronto ON",
    delivery_attention: "Site office",
  });
});
