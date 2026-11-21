import { expect, test } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";

/**
 * S-06-T06 — a rate-limited request (429 `request.rate_limited`, S-06-T05) is sent again by itself
 * after Retry-After, with the toast "You're going a little fast — retrying in N s" meanwhile.
 * Acceptance: toast and auto-retry observed. (The server's bucket: backend/tests/test_rate_limit.py.)
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";

test("a 429 shows the toast, then the page loads by itself", async ({ page }) => {
  await mockCsrf(page);
  let calls = 0;
  await page.route(`**/api/v1/o/${ORG}/settings`, (route) => {
    calls += 1;
    if (calls === 1)
      return route.fulfill({
        status: 429,
        headers: { "Retry-After": "2" },
        json: { code: "request.rate_limited", detail: "You're going a little fast." },
      });
    return route.fulfill({
      json: {
        legal_name: "",
        display_name: "Refined Interiors",
        industry: "",
        structure: "corporation",
        mailing_line1: "",
        mailing_line2: "",
        mailing_city: "",
        mailing_province: "",
        mailing_postal_code: "",
        phone: "",
        email: "",
        website: "",
        fye_month: 12,
        fye_day: 31,
        base_currency: "CAD",
        time_zone: "America/Toronto",
      },
    });
  });
  await page.goto(`/o/${ORG}/settings/general`);
  const toast = page.locator("[data-rate-limit-toast]");
  await expect(toast).toContainText("You're going a little fast — retrying in");
  await expect(page.getByText("Base currency: CAD (can't change)")).toBeVisible({ timeout: 8000 });
  expect(calls).toBe(2);
  await expect(toast).toBeEmpty({ timeout: 4000 });
});
