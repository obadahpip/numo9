import { expect, test } from "@playwright/test";

import { mockBillEditor } from "./bills-fixtures";

/**
 * E-02-T12 — the supplier invoice number already on another bill of the supplier shows inline
 * with a link to that bill (gap-24; the API side: backend/tests/test_bill_number_check.py).
 */
const ORG = "acme";
const OTHER = "b2b2b2b2-0000-4000-8000-000000000002";

test("inline duplicate-number message with a link", async ({ page }) => {
  await mockBillEditor(page);
  await page.route(`**/api/v1/o/${ORG}/bills/check-number*`, (r) => {
    const number = new URL(r.request().url()).searchParams.get("number");
    return r.fulfill({
      json:
        number === "CS-0042"
          ? {
              number,
              available: false,
              conflict: {
                id: OTHER,
                number: "BILL-0042",
                status: "awaiting_payment",
                date: "2026-09-12",
                url: `/o/${ORG}/purchases/bills/${OTHER}`,
                message: "Already used on BILL-0042 (12 Sep 2026)",
              },
            }
          : { number, available: true, conflict: null },
    });
  });
  await page.goto(`/o/${ORG}/purchases/bills/new`);
  const form = page.getByRole("form", { name: "New bill" });
  await form
    .getByRole("combobox", { name: "Supplier" })
    .selectOption({ label: "Cedar Supply Co." });
  const number = form.getByRole("textbox", { name: "Supplier invoice number" });
  await number.fill("CS-0042");
  await expect(page.getByText("Already used on BILL-0042 (12 Sep 2026)")).toBeVisible();
  await expect(number).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByRole("link", { name: "Open it" })).toHaveAttribute(
    "href",
    `/o/${ORG}/purchases/bills/${OTHER}`,
  );
  await number.fill("CS-0043");
  await expect(page.getByText("Already used on BILL-0042 (12 Sep 2026)")).toBeHidden();
});
