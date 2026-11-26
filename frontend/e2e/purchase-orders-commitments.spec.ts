import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { ORG } from "./purchase-orders-fixtures";

/**
 * E-01-T14 — commitment report: the export downloads the query on screen (grouping and dates),
 * and its rows and total are the screen's: the server writes both from one query
 * (backend/tests/test_purchase_order_api.py compares the CSV with the JSON).
 */
const REPORT = {
  by: "supplier",
  rows: [
    { key: "a", label: "Cedar Supply Co.", amount: "570.00", lines: 2, orders: 1, budget: null },
    { key: "b", label: "Maple Hardware Ltd", amount: "200.00", lines: 1, orders: 1, budget: null },
  ],
  total: "770.00",
  from: null,
  to: null,
};
const CSV =
  "\uFEFFSupplier,Open POs,Open lines,Open value,Budget\r\n" +
  "Cedar Supply Co.,1,2,570.00,\r\nMaple Hardware Ltd,1,1,200.00,\r\nTotal,,,770.00,\r\n";

test("export = screen", async ({ page }) => {
  await mockCsrf(page);
  const exported: string[] = [];
  await page.route(`**/api/v1/o/${ORG}/reports/commitments?*`, (r) => {
    const url = new URL(r.request().url());
    if (url.searchParams.get("export")) {
      exported.push(url.search);
      return r.fulfill({
        body: CSV,
        contentType: "text/csv; charset=utf-8",
        headers: { "Content-Disposition": 'attachment; filename="commitments-supplier.csv"' },
      });
    }
    return r.fulfill({ json: { ...REPORT, by: url.searchParams.get("by") ?? "account" } });
  });
  await page.goto(`/o/${ORG}/purchases/commitments`);
  await page.getByRole("combobox", { name: "Group by" }).selectOption("supplier");
  await expect(page.getByRole("columnheader", { name: "Supplier" })).toBeVisible();
  await expectAccessible(page);
  const screenRows = await page.getByRole("row").allInnerTexts();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Export CSV" }).click(),
  ]);
  const text = readFileSync(await download.path(), "utf-8");
  const lines = text
    .replace(/^\uFEFF/, "")
    .trim()
    .split(/\r?\n/);
  expect(exported[0]).toBe("?by=supplier&export=csv");
  expect(lines.slice(1).map((line) => line.split(",")[0])).toEqual(
    screenRows.slice(1).map((row) => row.split("\t")[0]),
  );
  expect(lines.at(-1)).toContain("770.00");
});
