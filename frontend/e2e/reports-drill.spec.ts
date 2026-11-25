import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { CATALOGUE, profitAndLoss, SALES_LINES } from "./reports-fixtures";

/** K-01-T14 — two clicks from a P&L figure to the invoice behind it. */
test("2 clicks from a P&L figure to the invoice", async ({ page }) => {
  await mockCsrf(page);
  await page.route("**/api/v1/o/acme/reports", (r) => r.fulfill({ json: CATALOGUE }));
  await page.route("**/api/v1/o/acme/reports/profit-and-loss/run*", (r) =>
    r.fulfill({ json: profitAndLoss(1) }),
  );
  await page.route("**/api/v1/o/acme/reports/profit-and-loss/drill*", (r) =>
    r.fulfill({ json: SALES_LINES }),
  );
  await page.goto("/o/acme/reports/profit-and-loss");
  const sales = page.getByRole("row", { name: /4000 · Sales/ });
  await sales.hover();
  await sales.getByRole("button", { name: "Show the lines of 4000 · Sales, Jan–Dec 2026" }).click(); // 1
  const drawer = page.getByRole("dialog", { name: "4000 · Sales" });
  await expect(drawer.getByText("1 line · total -$6,200.00")).toBeVisible();
  await expectAccessible(page);
  await drawer.getByRole("link", { name: "Open invoice" }).click(); // 2
  await expect(page).toHaveURL(/\/o\/acme\/sales\/invoices\/7f2c9a40-3b1e-4c8a-9d6f-1a2b3c4d5e6f/);
});
