import { expect, test, type Page } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";

/**
 * E-02-T15 — the purchases overview is the shared OverviewPage (gap-22: same component id as the
 * sales overview); a tile opens the bills list on the tab of the same key with the same count;
 * D-09-T10 (gap-05) — a card answering 500 shows what failed, Try again and the reference, and
 * Try again recovers. API side: backend/tests/test_bills_overview.py.
 */
const ORG = "acme";
const tiles = [
  { key: "draft", label: "Draft", count: 2, amount: "400.00", href: "" },
  { key: "awaiting_approval", label: "Awaiting approval", count: 1, amount: "700.00", href: "" },
  { key: "awaiting_payment", label: "Awaiting payment", count: 4, amount: "3700.00", href: "" },
  { key: "overdue", label: "Overdue", count: 3, amount: "2700.00", href: "" },
];
const aging = [
  { key: "current", label: "Current", count: 1, amount: "1000.00" },
  { key: "1_30", label: "1–30 days", count: 1, amount: "400.00" },
  { key: "31_60", label: "31–60 days", count: 1, amount: "2000.00" },
  { key: "61_90", label: "61–90 days", count: 0, amount: "0.00" },
  { key: "over_90", label: "Over 90 days", count: 1, amount: "300.00" },
];

async function mockOverview(page: Page, { agingFailures = 0 } = {}) {
  await mockCsrf(page);
  let failures = agingFailures;
  await page.route(`**/api/v1/o/${ORG}/bills/overview*`, (route) => {
    const section = new URL(route.request().url()).searchParams.get("section");
    if (section === "aging" && failures > 0) {
      failures -= 1;
      return route.fulfill({
        status: 500,
        headers: { "X-Request-ID": "req-gap05-0001" },
        json: { detail: "Server error" },
      });
    }
    const body =
      section === "tiles"
        ? { as_of: "2026-09-30", tiles }
        : section === "aging"
          ? { as_of: "2026-09-30", aging }
          : {
              as_of: "2026-09-30",
              top_suppliers: [
                {
                  id: "s1",
                  name: "Cedar Supply Co.",
                  owed: "3000.00",
                  overdue: "2000.00",
                  bills: 2,
                },
              ],
            };
    return route.fulfill({ json: body });
  });
  await page.route(`**/api/v1/o/${ORG}/bills?*`, (route) => {
    const tab = new URL(route.request().url()).searchParams.get("tab") ?? "all";
    return route.fulfill({
      json: {
        count: 3,
        page: 1,
        pages: 1,
        tab,
        counts: {},
        tabs: [
          { key: "all", label: "All", count: 8, amount: "0.00" },
          ...tiles.map(({ key, label, count, amount }) => ({ key, label, count, amount })),
          { key: "paid", label: "Paid", count: 1, amount: "999.00" },
          { key: "void", label: "Void", count: 0, amount: "0.00" },
        ],
        results: [],
      },
    });
  });
}

test("purchases overview is the shared OverviewPage (gap-22)", async ({ page }) => {
  await mockOverview(page);
  await page.goto(`/o/${ORG}/purchases`);
  const root = page.locator("[data-component=overview-page]");
  await expect(root).toHaveAttribute("data-overview", "purchases");
  await expect(page.getByRole("heading", { level: 1, name: "Purchases overview" })).toBeVisible();
});

test("a tile opens the bills list on the same tab with the same count", async ({ page }) => {
  await mockOverview(page);
  await page.goto(`/o/${ORG}/purchases`);
  await page.getByRole("link", { name: "Overdue: 3 bills, $2,700.00" }).click();
  await expect(page).toHaveURL(`/o/${ORG}/purchases/bills?tab=overdue`);
  const tab = page.getByRole("tab", { name: /Overdue/ });
  await expect(tab).toHaveAttribute("aria-selected", "true");
  await expect(tab).toContainText("3");
});

test("a card answering 500 shows Try again and the reference; Try again recovers (gap-05)", async ({
  page,
}) => {
  await mockOverview(page, { agingFailures: 1 });
  await page.goto(`/o/${ORG}/purchases`);
  const card = page.getByRole("region", { name: "Money going out" });
  const alert = card.getByRole("alert");
  await expect(alert).toContainText("Money going out couldn't be loaded");
  await expect(alert).toContainText("Reference: req-gap05-0001");
  await expect(alert).not.toContainText(/unable to load/i);
  // The rest of the page still works.
  await expect(page.getByRole("link", { name: /Overdue: 3 bills/ })).toBeVisible();
  await alert.getByRole("button", { name: "Try again" }).click();
  await expect(
    card.getByRole("img", { name: "Money going out by age: $3,700.00 owed" }),
  ).toBeVisible();
  await expect(card.getByRole("alert")).toHaveCount(0);
});

test.describe("@visual purchases overview (gap-22)", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("overview", async ({ page }) => {
    await page.clock.setFixedTime(new Date("2026-10-26T14:00:00-04:00"));
    await mockOverview(page);
    await page.goto(`/o/${ORG}/purchases`);
    await expect(page.getByRole("link", { name: "Cedar Supply Co." })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    await expect(page.locator("[data-component=overview-page]")).toHaveScreenshot(
      "purchases-overview.png",
    );
  });
});
