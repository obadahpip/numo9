import { expect, test } from "@playwright/test";

import { expectAccessible } from "./auth-helpers";
import { BILL, DOC, mockBillEditor, SUPPLIER } from "./bills-fixtures";

const ORG = "acme";

/**
 * E-02-T11 — bill editor split view: from a document of the inbox, the bill is entered beside
 * the PDF without leaving the page. The API side is tested in backend/tests/test_bill_api.py.
 */
test("enter a bill from its PDF without leaving the page", async ({ page }) => {
  const posted = await mockBillEditor(page);
  await page.goto(`/o/${ORG}/purchases/bills/new?document=${DOC}`);
  const preview = page.frameLocator('iframe[title="Preview of cedar-invoice-1001.pdf"]');
  await expect(page.locator('iframe[title="Preview of cedar-invoice-1001.pdf"]')).toBeVisible();
  void preview;
  const form = page.getByRole("form", { name: "New bill" });
  await form.getByRole("combobox", { name: "Supplier" }).selectOption(SUPPLIER);
  await form.getByRole("textbox", { name: "Supplier invoice number" }).fill("CS-1001");
  await page.getByRole("textbox", { name: "Description, line 1" }).fill("Tiles");
  await page.getByRole("combobox", { name: "Account, line 1" }).click();
  await page.getByRole("option", { name: /6100/ }).click();
  await expectAccessible(page);
  await form.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Saved as a draft.")).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/purchases/bills/${BILL}$`));
  // Still beside its document: the bill keeps the PDF on screen after the save.
  await expect(page.locator('iframe[title="Preview of cedar-invoice-1001.pdf"]')).toBeVisible();
  expect(posted[0]).toMatchObject({
    supplier: SUPPLIER,
    supplier_invoice_no: "CS-1001",
    document: DOC,
  });
});
