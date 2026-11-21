import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * V-04-T08 — practice home cards + drill links + error/retry. Acceptance: zero renders "0"; a card
 * opens the directory with the same filters in its address (shareable) and the directory asks the
 * API for exactly those filters. (Drill count = card count is tested against the real API:
 * backend/tests/test_dashboard_drilldown.py.)
 */
const PRACTICE = "6ca1b880-64f7-4053-80e3-0c3618895553";

const card = (
  key: string,
  title: string,
  count: number | null,
  extra: Record<string, unknown> = {},
) => ({
  key,
  title,
  description: "",
  kind: "count",
  status: count === null ? "error" : "ok",
  count,
  filters: null,
  href: "",
  items: [],
  ...extra,
});

test("cards, zero, a failing card with retry, and a drill-down to the directory", async ({
  page,
}) => {
  await mockCsrf(page);
  let calls = 0;
  await page.route("**/api/v1/practice/dashboard?*", (route) => {
    calls += 1;
    return route.fulfill({
      json: {
        practice: { id: PRACTICE, name: "Abuodeh CPA" },
        scope: "all",
        scopes: ["mine", "all"],
        widgets: [
          card("trials_ending", "Trials ending in 7 days", 3, {
            filters: { status: ["trial"], trial_ending: ["yes"] },
          }),
          card("read_only", "Read-only organisations", 0, { filters: { status: ["read_only"] } }),
          card("missing_bn", "Organisations without a BN", calls === 1 ? null : 2, {
            filters: calls === 1 ? null : { bn_missing: ["yes"] },
          }),
          {
            ...card("deadlines", "Deadlines in the next 30 days", 0),
            kind: "list",
          },
          {
            ...card("workload", "Workload", 1),
            kind: "workload",
            items: [
              { id: "u1", name: "Sam Patel", role: "accountant", organisations: 3, open_tasks: 0 },
            ],
          },
        ],
      },
    });
  });
  const directoryRequests: URL[] = [];
  await page.route("**/api/v1/practice/orgs?*", (route) => {
    directoryRequests.push(new URL(route.request().url()));
    return route.fulfill({
      json: {
        practice: { id: PRACTICE, name: "Abuodeh CPA" },
        count: 3,
        total: 6,
        page: 1,
        page_size: 2000,
        pages: 1,
        columns: ["name", "status"],
        results: [],
        facets: {},
      },
    });
  });
  await page.route("**/api/v1/practice/views**", (route) => route.fulfill({ json: [] }));

  await page.goto(`/p/${PRACTICE}`);
  await expect(page.getByRole("heading", { level: 1, name: "Practice home" })).toBeVisible();
  await expect(
    page.getByRole("navigation").getByRole("link", { name: "Dashboard" }),
  ).toHaveAttribute("aria-current", "page");
  const readOnly = page.locator('[data-widget="read_only"]');
  await expect(readOnly.locator("[data-count]")).toHaveText("0");
  const failed = page.locator('[data-widget="missing_bn"]');
  await expect(failed).toContainText("Couldn't load this figure.");
  await expectAccessible(page);
  await failed.getByRole("button", { name: "Try again: Organisations without a BN" }).click();
  await expect(page.locator('[data-widget="missing_bn"] [data-count]')).toHaveText("2");

  await page.getByRole("link", { name: "Open in directory: Trials ending in 7 days" }).click();
  await expect(page).toHaveURL(`/p/${PRACTICE}/directory?status=trial&trial_ending=yes`);
  await expect
    .poll(() => directoryRequests.at(-1)?.searchParams.getAll("trial_ending"))
    .toEqual(["yes"]);
  expect(directoryRequests.at(-1)?.searchParams.getAll("status")).toEqual(["trial"]);
});

test("customise the dashboard: the layout persists after a reload (V-04-T09)", async ({ page }) => {
  await mockCsrf(page);
  const layout = { order: [] as string[], hidden: [] as string[] };
  const all = [
    card("trials_ending", "Trials ending in 7 days", 3, { filters: { status: ["trial"] } }),
    card("read_only", "Read-only organisations", 0, { filters: { status: ["read_only"] } }),
    card("missing_bn", "Organisations without a BN", 2, { filters: { bn_missing: ["yes"] } }),
  ];
  await page.route("**/api/v1/practice/dashboard?*", (route) => {
    const rank = new Map(layout.order.map((key, index) => [key, index]));
    const widgets = [...all]
      .sort((a, b) => (rank.get(a.key) ?? 99) - (rank.get(b.key) ?? 99))
      .map((w) => ({ ...w, hidden: layout.hidden.includes(w.key) }));
    return route.fulfill({
      json: {
        practice: { id: PRACTICE, name: "Abuodeh CPA" },
        scope: "all",
        scopes: ["mine", "all"],
        layout,
        widgets,
      },
    });
  });
  await page.route("**/api/v1/practice/dashboard/layout?*", (route) => {
    Object.assign(layout, route.request().postDataJSON());
    return route.fulfill({ json: layout });
  });
  await page.goto(`/p/${PRACTICE}`);
  await page.getByRole("button", { name: "Customise dashboard" }).click();
  await page.getByRole("button", { name: "Move up: Organisations without a BN" }).click();
  await page.getByRole("button", { name: "Move up: Organisations without a BN" }).click();
  await page.getByRole("checkbox", { name: "Show Read-only organisations" }).uncheck();
  await expectAccessible(page);
  await page.getByRole("button", { name: "Save layout" }).click();
  await expect(page.getByText("Your dashboard layout is saved.")).toBeAttached();
  await page.reload();
  const cards = page.locator("[data-cards] [data-widget]");
  await expect(cards).toHaveCount(2);
  await expect(cards.first()).toHaveAttribute("data-widget", "missing_bn");
  expect(layout).toEqual({
    order: ["missing_bn", "trials_ending", "read_only"],
    hidden: ["read_only"],
  });
});
