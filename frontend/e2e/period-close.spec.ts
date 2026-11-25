import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * C-06-T08, T09 — period close: pills per module and month reflect the API, the grid is
 * keyboard navigable and axe-clean; a month's checklist links to the list that fixes each item;
 * closing asks with its consequences; reopen is for advisers (with a reason). Server side:
 * backend/tests/test_period_close_*.py.
 */
const ORG = "acme";
const BASE = `**/api/v1/o/${ORG}/period-close`;
const MODULES = [
  ["gl", "General ledger"],
  ["ar", "Sales and accounts receivable"],
  ["ap", "Purchases and accounts payable"],
];

function months(closedThrough: number) {
  return Array.from({ length: 12 }, (_, i) => {
    const m = String(i + 1).padStart(2, "0");
    const last = new Date(Date.UTC(2026, i + 1, 0)).getUTCDate();
    return {
      start: `2026-${m}-01`,
      end: `2026-${m}-${last}`,
      status: i < closedThrough ? "closed" : "open",
      close: i < closedThrough ? "close-gl-june" : null,
      past: i < 10,
    };
  });
}

async function mock(page: Page, { adviser }: { adviser: boolean }) {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  let closed = 6;
  await mockCsrf(page);
  await page.route(/\/api\/v1\/o\/acme\/period-close\/(\?.*)?$/, (r) =>
    r.fulfill({
      json: {
        fiscal_year: { start: "2026-01-01", end: "2026-12-31" },
        today: "2026-11-25",
        modules: MODULES.map(([module, label], i) => ({
          module,
          label,
          months: months(i === 0 ? closed : 0),
        })),
        closes: [
          {
            id: "close-gl-june",
            module: "gl",
            period_end: "2026-06-30",
            kind: "month",
            closed_by: { id: "u1", name: "Dana Lee" },
            closed_at: "2026-07-03T12:00:00Z",
            reopened_by: null,
            reopened_at: null,
            reason: "",
            entries: [],
          },
        ],
        year_end: null,
        is_adviser: adviser,
      },
    }),
  );
  await page.route(`${BASE}/checklist?*`, (r) =>
    r.fulfill({
      json: {
        period_end: "2026-07-31",
        items: [
          {
            key: "drafts",
            label: "Drafts dated in the period",
            count: 3,
            detail: {},
            link: `/o/${ORG}/accounting/journals?status=draft&from=2026-07-01&to=2026-07-31`,
          },
          {
            key: "awaiting_approval",
            label: "Waiting for approval",
            count: 0,
            detail: {},
            link: `/o/${ORG}/approvals`,
          },
          {
            key: "unfiled_tax",
            label: "Tax periods ended and not filed",
            count: 1,
            detail: {},
            link: `/o/${ORG}/settings/tax`,
          },
          {
            key: "exceptions",
            label: "Recurring journals skipped and automatic reversals not posted",
            count: 0,
            detail: {},
            link: `/o/${ORG}/accounting/journals/recurring`,
          },
        ],
      },
    }),
  );
  await page.route(`${BASE}/close`, (r) => {
    posts.push({ url: "close", body: jsonBody(r) });
    closed = 7;
    return r.fulfill({ status: 201, json: { id: "c2" } });
  });
  await page.route(`${BASE}/*/reopen`, (r) => {
    posts.push({ url: r.request().url(), body: jsonBody(r) });
    return r.fulfill({ json: { id: "close-gl-june" } });
  });
  return posts;
}

test.use({ viewport: { width: 1440, height: 900 } });

test("pills, keyboard, checklist links and closing a month", async ({ page }) => {
  const posts = await mock(page, { adviser: false });
  await page.goto(`/o/${ORG}/accounting/period-close`);
  const grid = page.getByRole("table", { name: "Close status by module and month" });
  await expect(grid.locator('[data-module="gl"] [data-status="closed"]')).toHaveCount(6);
  await expect(grid.locator('[data-module="ar"] [data-status="open"]')).toHaveCount(12);
  await expectAccessible(page);
  const june = grid.getByRole("button", { name: "General ledger, June 2026: Closed" });
  await june.focus();
  await page.keyboard.press("ArrowRight");
  const july = grid.getByRole("button", { name: "General ledger, July 2026: Open" });
  await expect(july).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(
    grid.getByRole("button", { name: /Sales and accounts receivable, July 2026/ }),
  ).toBeFocused();
  await july.click();
  const panel = page.locator("[data-checklist]");
  await expect(panel.getByText("Drafts dated in the period: 3")).toBeVisible();
  await expect(panel.locator('[data-item="drafts"] a')).toHaveAttribute(
    "href",
    `/o/${ORG}/accounting/journals?status=draft&from=2026-07-01&to=2026-07-31`,
  );
  await expect(panel.locator('[data-item="awaiting_approval"] a')).toHaveCount(0);
  await panel.getByRole("button", { name: "Close July 2026" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("advisers included");
  await dialog.getByRole("button", { name: "Close the period" }).click();
  await expect(dialog).toBeHidden();
  expect(posts[0]?.body).toEqual({ module: "gl", period_end: "2026-07-31" });
  await june.click();
  await expect(
    panel.getByText("Only your accountant (an adviser) can reopen a closed period."),
  ).toBeVisible();
});

test("an adviser reopens with a reason", async ({ page }) => {
  const posts = await mock(page, { adviser: true });
  await page.goto(`/o/${ORG}/accounting/period-close`);
  await page.getByRole("button", { name: "General ledger, June 2026: Closed" }).click();
  await page.locator("[data-checklist]").getByRole("button", { name: "Reopen" }).click();
  const dialog = page.getByRole("dialog");
  const confirm = dialog.getByRole("button", { name: "Reopen the period" });
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel(/Why is it reopened/).fill("Late supplier bill");
  await confirm.click();
  await expect(dialog).toBeHidden();
  expect(posts[0]?.body).toEqual({ reason: "Late supplier bill", force: false });
});
