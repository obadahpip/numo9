import { expect, test } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";
import { entitlements, mockEntitlements } from "./entitlements-fixtures";
import { CATALOGUE, profitAndLoss } from "./reports-fixtures";

/**
 * K-01-T18 — reports are in the global search and the command palette: "balance sheet" opens
 * the runner. The search entries (every registered report, gated by its feature key) are tested
 * on the real API in backend/tests/test_report_search.py.
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";

test.use({ viewport: { width: 1440, height: 900 } });

test("'balance sheet' in the palette opens the runner", async ({ page }) => {
  await mockCsrf(page);
  await mockEntitlements(page, ORG, entitlements());
  await page.route(`**/api/v1/o/${ORG}/my-permissions`, (r) =>
    r.fulfill({ json: { permissions: ["reports.reports.view"] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/search?*`, (route) => {
    const q = new URL(route.request().url()).searchParams.get("q") ?? "";
    return route.fulfill({
      json: {
        query: q,
        records: [],
        settings: [],
        reports: q.includes("balance")
          ? [
              {
                key: "reports.balance_sheet",
                title: "Balance sheet",
                url: `/o/${ORG}/reports/balance-sheet`,
                locked: false,
                reason: "",
              },
            ]
          : [],
        navigation: [],
      },
    });
  });
  await page.route(`**/api/v1/o/${ORG}/reports`, (r) => r.fulfill({ json: CATALOGUE }));
  await page.route(`**/api/v1/o/${ORG}/reports/balance-sheet/run*`, (r) =>
    r.fulfill({
      json: {
        ...profitAndLoss(1),
        report: "balance_sheet",
        header: { ...profitAndLoss(1).header, title: "Balance sheet" },
      },
    }),
  );
  await page.goto(`/o/${ORG}/reports`);
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: "Search" });
  await page.keyboard.type("balance sheet");
  const reports = dialog.getByRole("group", { name: "Reports" });
  await expect(reports.getByRole("option", { name: /Balance sheet/ })).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(`/o/${ORG}/reports/balance-sheet`);
  await expect(page.getByRole("heading", { name: "Balance sheet", level: 1 })).toBeVisible();
  await expect(page.getByRole("table", { name: "Balance sheet" })).toBeVisible();
});
