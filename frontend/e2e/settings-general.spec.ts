import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * A-05-T11 — Settings → General: Province select, Postal code mask, time zone, fiscal year end.
 * Acceptance: saves; validation inline — client rules (postal code, day) under the field before
 * any request, server rules (numeric-only legal name) on the field from the 400; the save sends
 * only the form's fields with the masked postal code; axe clean.
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}/settings`;

const SETTINGS = {
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
};

async function mock(page: Page) {
  await mockCsrf(page);
  const sent: Record<string, unknown>[] = [];
  await page.route(API, (route) => {
    if (route.request().method() === "PATCH") {
      const body = jsonBody(route);
      sent.push(body);
      if (body.legal_name === "1001633222")
        return route.fulfill({
          status: 400,
          json: {
            legal_name: [
              "A legal name has letters — enter it as registered, e.g. Refined Interiors Inc.",
            ],
          },
        });
      return route.fulfill({ json: { ...SETTINGS, ...body } });
    }
    return route.fulfill({ json: SETTINGS });
  });
  return sent;
}

test.use({ viewport: { width: 1280, height: 1000 } });

test("fill the address, validate inline, save", async ({ page }) => {
  const sent = await mock(page);
  await page.goto(`/o/${ORG}/settings/general`);
  await expect(page.getByRole("heading", { level: 1, name: "General" })).toBeVisible();
  await expect(page.getByText("Base currency: CAD (can't change)")).toBeVisible();
  await expectAccessible(page);

  await page.getByLabel("Street address or PO box").fill("100 King St W");
  await page.getByLabel("City").fill("Toronto");
  await page.getByRole("combobox", { name: "Province or territory" }).click();
  await page.getByRole("option", { name: "Ontario" }).click();
  const postal = page.getByLabel("Postal code");
  await postal.fill("m5x1a9");
  await expect(postal).toHaveValue("M5X 1A9"); // masked as typed
  await page.getByLabel("Fiscal year end: day").fill("45");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.locator('[data-field="fye_day"]')).toContainText("Enter a day from 1 to 31.");
  await expect(
    page.getByRole("link", { name: "Fiscal year end: day: Enter a day from 1 to 31." }),
  ).toBeVisible();
  expect(sent).toEqual([]); // client rules stop the request

  await page.getByLabel("Fiscal year end: day").fill("31");
  await page.getByLabel("Legal name").fill("1001633222");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.locator('[data-field="legal_name"]')).toContainText("A legal name has letters");

  await page.getByLabel("Legal name").fill("Refined Interiors Inc.");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.locator("[data-settings-status]")).toHaveText("Settings saved.");
  const last = sent[sent.length - 1]!;
  expect(last).toMatchObject({
    legal_name: "Refined Interiors Inc.",
    mailing_province: "ON",
    mailing_postal_code: "M5X 1A9",
    mailing_city: "Toronto",
    fye_month: 12,
    fye_day: 31,
    time_zone: "America/Toronto",
  });
  expect(last).not.toHaveProperty("base_currency");
});

test("founding organisation: the badge shows its number (U-08-T09)", async ({ page }) => {
  await mockCsrf(page);
  await page.route(API, (route) => route.fulfill({ json: { ...SETTINGS, founding_slot: 427 } }));
  await page.goto(`/o/${ORG}/settings/general`);
  const badge = page.getByText("Founding organisation #0427");
  await expect(badge).toBeVisible();
  await expect(page.locator('[data-founding-slot="427"]')).toHaveAttribute(
    "title",
    "One of the first 1,000 organisations: every Numo9 product is included.",
  );
  await expectAccessible(page);
});

test("not a founding organisation: no badge", async ({ page }) => {
  await mock(page);
  await page.goto(`/o/${ORG}/settings/general`);
  await expect(page.getByRole("heading", { level: 1, name: "General" })).toBeVisible();
  await expect(page.locator("[data-founding-slot]")).toHaveCount(0);
});
