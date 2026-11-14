import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, expectNoHorizontalScroll, jsonBody, mockCsrf } from "./auth-helpers";
import packages from "./fixtures/console-packages.json" with { type: "json" };
import fixture from "./fixtures/console-promo-codes.json" with { type: "json" };

/**
 * U-02-T11 — promo codes (`/console/promo-codes`): create, usage bar, expire. Acceptance: the
 * usage bar = redemptions / max. Fixture: the real API answer on 14 Nov 2026
 * (backend/tests/test_packages_fixtures.py): LAUNCH20 7 of 10, ACCT50 used up, FOREVER10 no
 * limit, SPRING expired.
 */
const API = "**/api/v1/platform/packages/promo-codes";

async function open(page: Page, codes: unknown = fixture) {
  await mockCsrf(page);
  await page.route("**/api/v1/platform/packages", (r) =>
    r.fulfill({ status: 200, json: packages }),
  );
  await page.route(API, (r) =>
    r.request().method() === "GET" ? r.fulfill({ status: 200, json: codes }) : r.fallback(),
  );
  await page.goto("/console/promo-codes");
}

test.use({ viewport: { width: 1280, height: 900 } });

test("lists codes with discount, duration, packages, usage bar = redemptions / max, status", async ({
  page,
}) => {
  await open(page);
  await expect(page.getByRole("heading", { level: 1, name: "Promo codes" })).toBeVisible();
  await expect(page.locator("tr[data-code]")).toHaveCount(4);

  const launch = page.locator('tr[data-code="LAUNCH20"]');
  await expect(launch).toContainText("20% off");
  await expect(launch).toContainText("3 months");
  await expect(launch).toContainText("Growth");
  await expect(launch).toContainText("7 of 10");
  await expect(launch).toContainText("31 Dec 2026");
  const bar = launch.getByRole("progressbar", { name: "Uses of LAUNCH20" });
  await expect(bar).toHaveAttribute("aria-valuenow", "7");
  await expect(bar).toHaveAttribute("aria-valuemax", "10");
  await expect(launch.getByTestId("usage-fill")).toHaveAttribute("style", "width: 70%;");
  await expect(launch.getByText("Active")).toBeVisible();

  const used = page.locator('tr[data-code="ACCT50"]');
  await expect(used).toContainText("$50.00 off");
  await expect(used).toContainText("Once");
  await expect(used).toContainText("Any package");
  await expect(used.getByTestId("usage-fill")).toHaveAttribute("style", "width: 100%;");
  await expect(used.getByText("Used up")).toBeVisible();
  await expect(used.getByRole("button", { name: /Expire/ })).toHaveCount(0);

  const forever = page.locator('tr[data-code="FOREVER10"]');
  await expect(forever).toContainText("3 · no limit");
  await expect(forever).toContainText("Never");
  await expect(forever.getByTestId("usage-fill")).toHaveAttribute("style", "width: 0%;");

  await expect(page.locator('tr[data-code="SPRING"]').getByText("Expired")).toBeVisible();
  await expectAccessible(page);
});

test("create a promo code in the dialog", async ({ page }) => {
  await open(page);
  let posted: Record<string, unknown> | null = null;
  await page.route(API, async (r) => {
    if (r.request().method() !== "POST") return r.fallback();
    posted = jsonBody(r);
    await r.fulfill({
      status: 201,
      json: {
        ...fixture.promo_codes[2],
        code: "PARTNER25",
        description: "Accountant partners",
        percent_off: 25,
        duration: "repeating",
        duration_label: "Number of months",
        duration_months: 6,
        max_redemptions: 40,
        redemptions_count: 0,
        packages: [{ code: "growth", name: "Growth" }],
      },
    });
  });
  await page.getByRole("button", { name: "New promo code" }).click();
  const dialog = page.getByRole("dialog", { name: "New promo code" });
  await dialog.getByLabel("Code").fill("partner25");
  await dialog.getByLabel("Description (optional)").fill("Accountant partners");
  await dialog.getByLabel("Percentage").fill("25");
  await dialog.getByRole("combobox", { name: "Duration" }).click();
  await page.getByRole("option", { name: "Number of months" }).click();
  await dialog.getByLabel("Months").fill("6");
  await dialog.getByLabel("Maximum uses (optional)").fill("40");
  await dialog.getByLabel("Expires on (optional)").fill("2027-06-30");
  await dialog.getByRole("checkbox", { name: "Growth" }).click();
  await expect(dialog.getByRole("checkbox", { name: "Legacy" })).toHaveCount(0); // retired
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Create code" }).click();

  await expect(dialog).toBeHidden();
  expect(posted).toEqual({
    code: "partner25",
    description: "Accountant partners",
    kind: "percent",
    percent_off: 25,
    amount_off_cents: null,
    duration: "repeating",
    duration_months: 6,
    max_redemptions: 40,
    expires_at: "2027-06-30T23:59:59",
    packages: ["growth"],
  });
  await expect(page.getByRole("status")).toHaveText("PARTNER25 created.");
  await expect(page.locator('tr[data-code="PARTNER25"]')).toContainText("0 of 40");
});

test("fixed amount, local checks and the API's field errors", async ({ page }) => {
  await open(page);
  await page.route(API, (r) =>
    r.request().method() === "POST"
      ? r.fulfill({
          status: 400,
          json: { code: ["The promo code LAUNCH20 is taken. Choose another code."] },
        })
      : r.fallback(),
  );
  await page.getByRole("button", { name: "New promo code" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("radio", { name: "Fixed amount off" }).click();
  await dialog.getByRole("button", { name: "Create code" }).click();
  await expect(dialog.getByText("Enter an amount greater than $0.00.")).toBeVisible();
  await dialog.getByLabel("Code").fill("LAUNCH20");
  await dialog.getByLabel("Amount off (CAD)").fill("50");
  await dialog.getByRole("button", { name: "Create code" }).click();
  await expect(
    dialog.getByText("The promo code LAUNCH20 is taken. Choose another code."),
  ).toBeVisible();
  await expect(dialog.getByLabel("Code")).toHaveAttribute("aria-invalid", "true");
});

test("expire ends an active code now", async ({ page }) => {
  await open(page);
  await page.route(`${API}/LAUNCH20/expire`, async (r) => {
    jsonBody(r);
    await r.fulfill({
      status: 200,
      json: { ...fixture.promo_codes[2], status: "expired", status_label: "Expired" },
    });
  });
  const launch = page.locator('tr[data-code="LAUNCH20"]');
  await launch.getByRole("button", { name: "Expire LAUNCH20 now" }).click();
  await expect(page.getByRole("status")).toHaveText(
    "LAUNCH20 has expired. Redemptions already made are kept.",
  );
  await expect(launch.getByText("Expired")).toBeVisible();
  await expect(launch.getByRole("button", { name: /Expire/ })).toHaveCount(0);
  await expect(launch).toContainText("7 of 10");
});

test("empty list and refusal", async ({ page }) => {
  await open(page, { promo_codes: [] });
  await expect(page.getByText("No promo codes yet")).toBeVisible();
  await page.unroute(API);
  await page.route(API, (r) =>
    r.fulfill({
      status: 403,
      json: { code: "permission.denied", detail: "You don't have permission to manage packages." },
    }),
  );
  await page.reload();
  await expect(
    page.getByRole("heading", { level: 1, name: "You can't manage packages and prices" }),
  ).toBeVisible();
});

test("fits a phone screen", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 });
  await open(page);
  await expect(page.locator("tr[data-code]")).toHaveCount(4);
  await expectNoHorizontalScroll(page);
});
