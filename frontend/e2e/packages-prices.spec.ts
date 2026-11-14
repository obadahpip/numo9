import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";
import products from "./fixtures/catalogue-products.json" with { type: "json" };
import fixture from "./fixtures/console-packages.json" with { type: "json" };

/**
 * U-02-T10 — price timeline + future-dated price dialog on `/console/packages/<code>`.
 * Acceptance: the dialog shows the affected-subscriptions count from the API; the timeline marks
 * today. Fixture: the real API answer on 14 Nov 2026 (backend/tests/test_packages_fixtures.py):
 * Growth monthly $39.00 until 30 Nov 2026 then $49.00 (scheduled), annual $468.00.
 */
type Pkg = Record<string, unknown>;
const API = "**/api/v1/platform/packages/growth";
const growth = fixture.packages.find((p) => p.code === "growth")! as Pkg;

async function open(page: Page, pkg: Pkg = growth) {
  await mockCsrf(page);
  await page.route("**/api/v1/platform/catalogue/products", (r) =>
    r.fulfill({ status: 200, json: products }),
  );
  await page.route(API, (r) => r.fulfill({ status: 200, json: pkg }));
  await page.goto("/console/packages/growth");
  await expect(page.getByTestId("price-timeline")).toBeVisible();
}

test.use({ viewport: { width: 1280, height: 900 } });

test("timeline shows each version per interval and marks today", async ({ page }) => {
  await open(page);
  const timeline = page.getByTestId("price-timeline");
  const monthly = timeline.locator('[data-interval="month"]');
  await expect(monthly.locator("ol > li")).toHaveCount(2);
  const current = monthly.locator('ol > li[data-state="current"]');
  await expect(current).toHaveText("$39.00");
  await expect(current).toHaveAttribute(
    "aria-label",
    "$39.00 from 1 Jan 2026 until 30 Nov 2026 — in force today",
  );
  await expect(monthly.locator('ol > li[data-state="scheduled"]')).toHaveAttribute(
    "aria-label",
    "$49.00 from 1 Dec 2026, no end date — scheduled",
  );
  await expect(monthly.getByTestId("today-marker")).toContainText("Today 14 Nov 2026");
  await expect(timeline.locator('[data-interval="year"] ol > li')).toHaveCount(1);
  await expect(timeline.locator('[data-interval="year"]')).toContainText("No end date");
  // the scheduled version can be deleted; the one in force can't
  await expect(
    monthly.getByRole("button", { name: "Delete the $49.00 price starting 1 Dec 2026" }),
  ).toBeVisible();
  await expect(monthly.getByRole("button", { name: /Delete the \$39\.00/ })).toHaveCount(0);
  await expectAccessible(page);
});

test("schedule dialog shows the affected subscriptions from the API, then schedules", async ({
  page,
}) => {
  await open(page);
  const impactRequests: string[] = [];
  await page.route("**/api/v1/platform/packages/growth/prices/impact**", (r) => {
    impactRequests.push(r.request().url());
    return r.fulfill({
      status: 200,
      json: {
        affected_subscriptions: 128,
        current: (growth.prices as Pkg[])[1],
      },
    });
  });
  let posted: Record<string, unknown> | null = null;
  const after: Pkg = {
    ...growth,
    prices: [
      ...(growth.prices as Pkg[]).slice(0, 1),
      { ...(growth.prices as Pkg[])[1], effective_to: "2027-03-01" },
      {
        id: "00000000-0000-4000-8000-000000000099",
        interval: "month",
        interval_label: "Monthly",
        amount_cents: 5500,
        currency: "CAD",
        tax_behaviour: "exclusive",
        effective_from: "2027-03-01",
        effective_to: null,
        state: "scheduled",
      },
      ...(growth.prices as Pkg[]).slice(2),
    ],
  };
  await page.route("**/api/v1/platform/packages/growth/prices", async (r) => {
    posted = jsonBody(r);
    await r.fulfill({
      status: 201,
      json: { price: (after.prices as Pkg[])[2], affected_subscriptions: 128, package: after },
    });
  });

  await page.getByRole("button", { name: "Schedule a price change" }).click();
  const dialog = page.getByRole("dialog", { name: "Schedule a price change" });
  await dialog.getByLabel("New price (CAD)").fill("55");
  await dialog.getByLabel("Starts on").fill("2027-03-01");
  const impact = dialog.getByTestId("price-impact");
  await expect(impact).toContainText("128 subscriptions affected at their next renewal");
  await expect(impact).toContainText("Renewals before 1 Mar 2027 keep $49.00.");
  await expect(impact).toContainText("Grandfathered subscriptions never change.");
  expect(impactRequests.at(-1)).toContain("interval=month&effective_from=2027-03-01");
  await expectAccessible(page);

  await dialog.getByRole("button", { name: "Schedule price" }).click();
  await expect(dialog).toBeHidden();
  expect(posted).toEqual({ interval: "month", amount_cents: 5500, effective_from: "2027-03-01" });
  await expect(page.getByRole("status")).toHaveText(
    "$55.00 monthly price scheduled from 1 Mar 2027.",
  );
  const monthly = page.locator('[data-interval="month"]');
  await expect(monthly.locator("ol > li")).toHaveCount(3);
  await expect(monthly.locator('ol > li[data-state="scheduled"]').last()).toHaveText("$55.00");
});

test("annual interval and the API's errors in the dialog", async ({ page }) => {
  await open(page);
  await page.route("**/api/v1/platform/packages/growth/prices/impact**", (r) =>
    r.fulfill({ status: 200, json: { affected_subscriptions: 0, current: null } }),
  );
  await page.route("**/api/v1/platform/packages/growth/prices", (r) =>
    r.fulfill({
      status: 400,
      json: {
        effective_from: [
          "A annual price already starts on 2027-01-01. Choose a later date, or delete that scheduled price first.",
        ],
      },
    }),
  );
  await page.getByRole("button", { name: "Schedule a price change" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("combobox", { name: "Billing interval" }).click();
  await page.getByRole("option", { name: "Annual" }).click();
  await dialog.getByRole("button", { name: "Schedule price" }).click();
  await expect(dialog.getByText("Enter an amount, for example 49.00.")).toBeVisible();
  await expect(dialog.getByText("Choose the date the new price starts.")).toBeVisible();
  await dialog.getByLabel("New price (CAD)").fill("$490.00");
  await dialog.getByLabel("Starts on").fill("2026-12-15");
  await expect(dialog.getByTestId("price-impact")).toContainText("No subscriptions affected yet");
  await dialog.getByRole("button", { name: "Schedule price" }).click();
  await expect(dialog.getByText(/already starts on 2027-01-01/)).toBeVisible();
  await expect(dialog.getByLabel("Starts on")).toHaveAttribute("aria-invalid", "true");
});

test("a scheduled price can be deleted", async ({ page }) => {
  await open(page);
  let deleted = "";
  const scheduled = (growth.prices as Pkg[])[1]!;
  await page.route(`**/api/v1/platform/packages/growth/prices/${scheduled.id as string}`, (r) => {
    deleted = r.request().method();
    return r.fulfill({ status: 204, body: "" });
  });
  await page.unroute(API);
  await page.route(API, (r) =>
    r.fulfill({
      status: 200,
      json: {
        ...growth,
        prices: [
          { ...(growth.prices as Pkg[])[0], effective_to: null },
          ...(growth.prices as Pkg[]).slice(2),
        ],
      },
    }),
  );
  await page.getByRole("button", { name: "Delete the $49.00 price starting 1 Dec 2026" }).click();
  await expect(page.getByRole("status")).toHaveText("The scheduled price was deleted.");
  expect(deleted).toBe("DELETE");
  await expect(page.locator('[data-interval="month"] ol > li')).toHaveCount(1);
});
