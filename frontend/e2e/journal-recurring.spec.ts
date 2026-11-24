import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * C-04-T11 — recurring journal editor: the "Next 6 dates" are exactly the backend preview of
 * the schedule built on screen (the generator the hourly job uses; the generator itself:
 * backend/tests/test_recurring_occurrences.py), refreshed when the schedule changes.
 */
const ORG = "acme";
const MONTHLY = [
  "2026-06-30",
  "2026-07-31",
  "2026-08-31",
  "2026-09-30",
  "2026-10-31",
  "2026-11-30",
];
const QUARTERLY = [
  "2026-07-31",
  "2026-10-31",
  "2027-01-31",
  "2027-04-30",
  "2027-07-31",
  "2027-10-31",
];

test.use({ viewport: { width: 1440, height: 900 } });

test("the preview shows the backend's dates for the schedule built", async ({ page }) => {
  await mockCsrf(page);
  const asked: { rrule: string; start_date: string; count: number }[] = [];
  await page.route(`**/api/v1/o/${ORG}/accounts?*`, (r) =>
    r.fulfill({ json: { count: 0, results: [] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/journals/recurring`, (r) =>
    r.fulfill({ json: { results: [] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/journals/recurring/preview`, (r) => {
    const body = r.request().postDataJSON() as { rrule: string; start_date: string; count: number };
    asked.push(body);
    return r.fulfill({ json: { dates: body.rrule.endsWith("INTERVAL=3") ? QUARTERLY : MONTHLY } });
  });
  await page.goto(`/o/${ORG}/accounting/journals/recurring`);
  await expect(page.getByRole("heading", { name: "No recurring journals yet" })).toBeVisible();
  await page.getByRole("button", { name: "New recurring journal" }).click();
  await page.getByLabel("Starts on").fill("2026-01-31");

  const preview = page.locator("[data-preview] [data-date]");
  await expect(preview).toHaveCount(6);
  expect(await preview.evaluateAll((els) => els.map((e) => e.getAttribute("data-date")))).toEqual(
    MONTHLY,
  );
  await page.getByLabel("Unit").selectOption("quarterly");
  await expect(page.locator("[data-preview] [data-date]").first()).toHaveAttribute(
    "data-date",
    QUARTERLY[0]!,
  );
  expect(
    await page
      .locator("[data-preview] [data-date]")
      .evaluateAll((els) => els.map((e) => e.getAttribute("data-date"))),
  ).toEqual(QUARTERLY);
  expect(asked.at(-1)).toMatchObject({
    rrule: "FREQ=MONTHLY;INTERVAL=3",
    start_date: "2026-01-31",
    count: 6,
  });
  await expectAccessible(page);
});
