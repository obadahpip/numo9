import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * E-04-T09 — the claimant's form on a phone (390 px): a receipt with a photo (the camera input),
 * a category chip, a trip with its amount shown live (E-04-T10), then Submit. Rules on the
 * server: backend/tests/test_expense_claim_api.py.
 */
const ORG = "acme";
const ID = "e1e1e1e1-0000-4000-8000-000000000001";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

const categories = {
  categories: [
    { id: "c-travel", code: "6200", name: "Travel", used: 3, itc_restriction_pct: null },
    {
      id: "c-meals",
      code: "6010",
      name: "Meals and entertainment",
      used: 1,
      itc_restriction_pct: "50",
    },
    { id: "c-office", code: "6080", name: "Office supplies", used: 0, itc_restriction_pct: null },
  ],
  tax_codes: [{ id: "t-on", code: "purchase.ON.standard", name: "HST 13% (ON)" }],
  default_tax_code: "t-on",
};

const rate = {
  date: "2026-06-15",
  region: "provinces",
  first_tier_rate: "0.73",
  second_tier_rate: "0.67",
  tier_threshold_km: 5000,
  year_to_date_km: "0",
};

test("an employee submits a claim on a 390 px phone", async ({ page }) => {
  await mockCsrf(page);
  let created: Record<string, unknown> | null = null;
  let submitted = false;
  await page.route(`**/api/v1/o/${ORG}/expense-claims/categories`, (r) =>
    r.fulfill({ json: categories }),
  );
  await page.route(`**/api/v1/o/${ORG}/expense-claims/mileage-rate**`, (r) =>
    r.fulfill({ json: rate }),
  );
  await page.route(`**/api/v1/o/${ORG}/expense-claims/receipts`, (r) =>
    r.fulfill({
      status: 201,
      json: {
        document: { id: "d1", name: "receipt.jpg" },
        upload: { url: "https://bucket.test/upload", fields: { key: "k" } },
      },
    }),
  );
  await page.route("https://bucket.test/upload", (r) => r.fulfill({ status: 204, body: "" }));
  await page.route(`**/api/v1/o/${ORG}/expense-claims/receipts/d1/finalize`, (r) =>
    r.fulfill({ json: { id: "d1", name: "receipt.jpg", duplicate: false } }),
  );
  await page.route(`**/api/v1/o/${ORG}/expense-claims/${ID}/submit`, (r) => {
    submitted = true;
    return r.fulfill({ json: { id: ID, number: "EXP-0001", status: "submitted" } });
  });
  await page.route(`**/api/v1/o/${ORG}/expense-claims`, (r) => {
    created = r.request().postDataJSON() as Record<string, unknown>;
    return r.fulfill({ status: 201, json: { id: ID, number: "", status: "draft" } });
  });
  await page.route(`**/api/v1/o/${ORG}/expense-claims/${ID}`, (r) =>
    r.fulfill({ json: { id: ID, number: "EXP-0001", status: "submitted" } }),
  );

  await page.goto(`/o/${ORG}/purchases/expense-claims/new`);
  await expect(page.getByRole("heading", { name: "New expense claim" })).toBeVisible();
  await page.getByLabel("What is this claim for?").fill("Kingston client visit");
  await page.getByLabel("Merchant").fill("Bistro 21");
  await page.getByLabel("Amount paid (tax included)").fill("56.50");
  await page.getByRole("button", { name: "Meals and entertainment" }).tap();
  await page.getByLabel("Take a photo or choose a file").setInputFiles({
    name: "receipt.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xe0]),
  });
  await expect(page.getByText("Attached: receipt.jpg")).toBeVisible();
  await page.getByRole("button", { name: "Add a trip" }).tap();
  await page.getByLabel("From").fill("Office");
  await page.getByLabel("To", { exact: true }).fill("Kingston");
  await page.getByLabel("Distance (km)").fill("100");
  await expect(page.getByText("$73.00")).toBeVisible(); // live CRA amount (E-04-T10)
  // Nothing overflows the phone's width.
  const width = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(width).toBeLessThanOrEqual(390);
  await expectAccessible(page);
  await page.getByRole("button", { name: "Submit for approval" }).tap();
  await expect.poll(() => submitted).toBe(true);
  expect(created).toMatchObject({ title: "Kingston client visit" });
  await expect(page).toHaveURL(new RegExp(`/purchases/expense-claims/${ID}$`));
});
