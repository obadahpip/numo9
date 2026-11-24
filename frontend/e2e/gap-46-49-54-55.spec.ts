import { expect, test, type Page } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";
import { CATALOGUE, EMPTY_PNL, profitAndLoss } from "./reports-fixtures";

/**
 * K-01-T19 — the report engine's gaps on screen (the data side: backend/tests/test_report_gaps.py):
 * - gap-46: the runner filters by tracking (the filter goes to the run and the drill-down);
 * - gap-49: one basis — the chip says where the basis comes from, and an override says so;
 * - gap-54: one engine — financial and tax reports in one home, one runner URL scheme;
 * - gap-55: an empty period says "No activity in this period" (never "–"), a future period end
 *   says "Year to date — unaudited", the header prints the legal name.
 */
async function mock(page: Page, body: (url: URL) => unknown) {
  await mockCsrf(page);
  const runs: URL[] = [];
  await page.route("**/api/v1/o/acme/reports", (r) => r.fulfill({ json: CATALOGUE }));
  await page.route("**/api/v1/o/acme/reports/*/run*", (r) => {
    const url = new URL(r.request().url());
    runs.push(url);
    return r.fulfill({ json: body(url) });
  });
  return runs;
}

test("gap-46: the tracking filter goes to the report run", async ({ page }) => {
  const runs = await mock(page, () => profitAndLoss(1));
  await page.goto("/o/acme/reports/profit-and-loss");
  await page.getByRole("textbox", { name: "Tracking" }).fill("region:east");
  await page.getByRole("button", { name: "Update" }).click();
  await expect.poll(() => runs.at(-1)?.searchParams.get("tracking")).toBe("region:east");
});

test("gap-49: the basis chip names its source, an override is labelled", async ({ page }) => {
  await mock(page, (url) => {
    const pnl = profitAndLoss(1);
    const basis = url.searchParams.get("basis");
    return basis
      ? { ...pnl, header: { ...pnl.header, basis_label: "Basis: Cash (this report)" } }
      : pnl;
  });
  await page.goto("/o/acme/reports/profit-and-loss");
  await expect(page.getByText("Basis: Accrual (organisation default)")).toBeVisible();
  await page.getByRole("combobox", { name: "Basis" }).click();
  await page.getByRole("option", { name: "Cash" }).click();
  await page.getByRole("button", { name: "Update" }).click();
  await expect(page.getByText("Basis: Cash (this report)")).toBeVisible();
});

test("gap-54: financial and tax reports in one home and one runner", async ({ page }) => {
  await mock(page, () => profitAndLoss(1));
  await page.goto("/o/acme/reports");
  const list = page.getByRole("list", { name: "Reports" });
  for (const [name, slug] of [
    ["Profit and loss", "profit-and-loss"],
    ["Balance sheet", "balance-sheet"],
    ["GST/HST summary", "gst-hst-summary"],
  ]) {
    await expect(list.getByRole("link", { name: name! })).toHaveAttribute(
      "href",
      `/o/acme/reports/${slug}`,
    );
  }
});

test("gap-55: no activity hint, never a dash; year-to-date label; legal name", async ({ page }) => {
  await mock(page, () => ({
    ...EMPTY_PNL,
    header: {
      ...EMPTY_PNL.header,
      period_label: "1 Apr 2026 to 31 Mar 2027",
      status_label: "Year to date — unaudited",
    },
  }));
  await page.goto("/o/acme/reports/profit-and-loss");
  await expect(page.getByRole("status").getByText("No activity in this period")).toBeVisible();
  const table = page.getByRole("table", { name: "Profit and loss" });
  // The column heading is a date range ("Jan–Dec 2026"); no cell is ever a dash.
  await expect(table.locator("tbody")).not.toContainText("–");
  await expect(table.getByText("$0.00")).toBeVisible();
  await expect(page.getByText("Year to date — unaudited")).toBeVisible();
  await expect(page.getByText("Refined Interiors Inc.")).toBeVisible();
});
