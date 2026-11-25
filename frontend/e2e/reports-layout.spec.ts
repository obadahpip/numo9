import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { CATALOGUE, profitAndLoss } from "./reports-fixtures";

/**
 * K-01-T15 — layout editor: rename a row, publish; the published version is listed on the
 * report home and opens as its immutable snapshot (the API's immutability is tested in
 * backend/tests/test_report_api.py).
 */
test("a published version is listed and immutable", async ({ page }) => {
  await mockCsrf(page);
  const id = "5d1c0c9e-2b3a-4c5d-8e9f-0a1b2c3d4e5f";
  let layout: Record<string, unknown> | null = null;
  const snapshot = profitAndLoss(1);
  await page.route("**/api/v1/o/acme/reports", (r) =>
    r.fulfill({ json: { ...CATALOGUE, published: layout ? [layout] : [] } }),
  );
  await page.route("**/api/v1/o/acme/reports/profit-and-loss/layouts", async (r) => {
    const body = r.request().postDataJSON() as Record<string, unknown>;
    layout = {
      id,
      report: "profit_and_loss",
      status: "draft",
      version: 1,
      practice: null,
      published_at: null,
      updated_at: null,
      ...body,
    };
    await r.fulfill({ status: 201, json: layout });
  });
  await page.route(`**/api/v1/o/acme/reports/layouts/${id}/publish`, async (r) => {
    layout = { ...layout, status: "published", published_at: "2026-08-01T12:00:00Z" };
    await r.fulfill({ json: layout });
  });
  await page.route("**/api/v1/o/acme/reports/profit-and-loss/run*", (r) => {
    const withLayout = new URL(r.request().url()).searchParams.get("layout");
    if (withLayout && layout) {
      const rows = snapshot.rows.map((row) =>
        row.key === "account:5400" ? { ...row, label: "Office rent" } : row,
      );
      return r.fulfill({ json: { ...snapshot, rows, layout } });
    }
    return r.fulfill({ json: snapshot });
  });

  await page.goto("/o/acme/reports/profit-and-loss");
  await page.getByRole("button", { name: "Edit layout" }).click();
  const panel = page.getByRole("complementary", { name: "Edit layout" });
  await panel.getByRole("textbox", { name: "Layout name" }).fill("Board pack");
  await panel.getByRole("textbox", { name: "Label for 5400 · Rent" }).fill("Office rent");
  await expectAccessible(page);
  await panel.getByRole("button", { name: "Publish" }).click();
  await expect(panel.getByText("Published version 1.")).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "Office rent" })).toBeVisible();
  await expect(page.getByText(/later postings don't change it/)).toBeVisible();

  await page.goto("/o/acme/reports");
  await page.getByRole("tab", { name: /Published/ }).click();
  await page.getByRole("link", { name: "Board pack" }).click();
  await expect(page).toHaveURL(new RegExp(`layout=${id}`));
  await expect(page.getByText("Layout: Board pack (version 1)")).toBeVisible();
  await page.getByRole("button", { name: "Edit layout" }).click();
  await expect(
    page.getByText("Version 1 is published and can't be changed. Saving starts version 2."),
  ).toBeVisible();
});
