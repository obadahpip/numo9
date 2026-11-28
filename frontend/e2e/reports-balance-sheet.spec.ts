import { expect, test } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";
import { balanceSheet, CATALOGUE } from "./reports-fixtures";

/**
 * K-02-T13 — statement-specific defaults and toggles: the balance sheet opens **as at today**
 * (not the end of the last financial year), the account-code and zero-balance toggles, and the
 * note on a reclassified overdraft (K-02-T04).
 */
function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

test.use({ viewport: { width: 1440, height: 900 } });

test("the balance sheet opens as at today, with codes, zero rows and the overdraft note", async ({
  page,
}) => {
  await mockCsrf(page);
  const runs: URL[] = [];
  await page.route("**/api/v1/o/acme/reports", (r) => r.fulfill({ json: CATALOGUE }));
  await page.route("**/api/v1/o/acme/reports/*/run*", (r) => {
    const url = new URL(r.request().url());
    runs.push(url);
    return r.fulfill({ json: balanceSheet(url.searchParams.get("as_of") ?? "") });
  });
  await page.goto("/o/acme/reports/balance-sheet");
  await expect.poll(() => runs[0]?.searchParams.get("as_of")).toBe(today());
  await expect(page.getByLabel("As at")).toHaveValue(today());

  const table = page.getByRole("table");
  await expect(table).toContainText("1000 · Chequing");
  await expect(table).toContainText("Bank overdraft — Petty Cash");
  await expect(table).toContainText("(ASPE 1510)");
  await expect(page.locator("[data-reclassification-note]")).toBeVisible();

  await page.getByRole("switch", { name: "Show account codes" }).click();
  await expect(table).not.toContainText("1000 · Chequing");
  await expect(table).toContainText("Chequing");

  await expect(table).not.toContainText("Old float");
  await page.getByRole("switch", { name: "Show zero rows" }).click();
  await expect(table).toContainText("Old float");
});
