import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * A-05-T12 — Settings → Tax registrations: one page, a repeater, a history drawer per row
 * (since G-06-T08 the first card of the tax settings page; the API is tax/registrations).
 * Acceptance: every statutory number is on this one page — BN, program accounts and provincial
 * numbers listed together and edited here; the server's rules land on the row's field (invalid
 * BN); add, save, remove; each row opens its history (A-04-T10); axe clean. ("No tax setting
 * elsewhere": the settings navigation has exactly one tax entry, this page.)
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}/tax/registrations`;

const BN = {
  id: "aaaaaaaa-0000-4000-8000-000000000001",
  type: "bn",
  type_label: "Business Number (BN)",
  number: "123456782",
  display_number: "123456782",
  effective_from: "2020-01-01",
  effective_to: null,
  status: "active",
  status_label: "Registered",
  cra_approval_ref: "",
};

async function mock(page: Page) {
  await mockCsrf(page);
  const calls: { method: string; body?: Record<string, unknown>; url: string }[] = [];
  await page.route(API, (route) => {
    const method = route.request().method();
    if (method === "POST") {
      const body = jsonBody(route);
      calls.push({ method, body, url: route.request().url() });
      if (body.number === "123456789")
        return route.fulfill({
          status: 400,
          json: {
            number: ["123456789 isn't a valid Business Number: the check digit doesn't match."],
          },
        });
      return route.fulfill({
        status: 201,
        json: {
          ...BN,
          id: "aaaaaaaa-0000-4000-8000-000000000002",
          type: "rt",
          type_label: "GST/HST program account (RT)",
          number: body.number,
          display_number: "123456782 RT 0001",
        },
      });
    }
    return route.fulfill({ json: { results: [BN] } });
  });
  // The page is the tax settings hub (G-06-T08): the registrations are its first card.
  await page.route(`**/api/v1/o/${ORG}/tax/settings`, (route) =>
    route.fulfill({
      json: {
        basis: "accrual",
        rounding_mode: "line",
        quick_method: false,
        quick_method_from: null,
        default_codes: {},
        restricted_itc_accounts: [],
        registered: true,
      },
    }),
  );
  await page.route(`${API}/*`, (route) => {
    calls.push({ method: route.request().method(), url: route.request().url() });
    return route.request().method() === "DELETE"
      ? route.fulfill({ status: 204, body: "" })
      : route.fulfill({ json: { ...BN, ...jsonBody(route) } });
  });
  const record = {
    type: "orgsettings.TaxRegistration",
    type_label: "Tax registration",
    id: BN.id,
    label: "BN",
  };
  const viewer = { time_format: "12h", time_zone: "America/Toronto", locale: "en-ca" };
  await page.route(`**/api/v1/o/${ORG}/audit/records/**`, (route) =>
    route.fulfill({ json: { record, results: [], next: null, viewer } }),
  );
  return calls;
}

test.use({ viewport: { width: 1280, height: 1000 } });

test("repeater: add with server validation, save, remove, history", async ({ page }) => {
  const calls = await mock(page);
  await page.goto(`/o/${ORG}/settings/registrations`);
  await expect(
    page.getByRole("heading", { level: 1, name: "Tax registrations and settings" }),
  ).toBeVisible();
  await expect(
    page.locator('[data-registration="aaaaaaaa-0000-4000-8000-000000000001"]'),
  ).toBeVisible();
  const nav = page.getByRole("navigation", { name: "Settings sections" });
  // Tax registrations and Tax codes (G-01-T12) until the tax settings hub (G-06) joins them.
  await expect(nav.getByRole("link", { name: /tax/i })).toHaveText([
    "Tax registrations",
    "Tax codes",
  ]);
  await expectAccessible(page);

  await page.getByRole("button", { name: "Add registration" }).click();
  const fresh = page.locator('[data-registration="new"]');
  await fresh.getByRole("combobox", { name: "Registration" }).click();
  await page.getByRole("option", { name: "GST/HST program account (RT)" }).click();
  await fresh.getByLabel("Number").fill("123456789");
  await fresh.getByRole("button", { name: "Save New registration" }).click();
  await expect(fresh).toContainText("the check digit doesn't match");
  await fresh.getByLabel("Number").fill("123456782RT0001");
  await fresh.getByRole("button", { name: "Save New registration" }).click();
  await expect(page.locator("[data-registrations-status]")).toHaveText(
    "GST/HST program account (RT) saved.",
  );
  await expect(page.locator("[data-registration]")).toHaveCount(2);
  expect(calls.filter((c) => c.method === "POST").map((c) => c.body?.type)).toEqual(["rt", "rt"]);

  const bnRow = page.locator('[data-registration="aaaaaaaa-0000-4000-8000-000000000001"]');
  await bnRow.getByRole("button", { name: "History" }).click();
  await expect(
    page.getByRole("dialog", { name: "History of Business Number (BN) 123456782" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");

  await bnRow.getByRole("button", { name: "Remove Business Number (BN)" }).click();
  await expect(page.locator("[data-registration]")).toHaveCount(1);
  expect(calls.some((c) => c.method === "DELETE" && c.url.endsWith("000000000001"))).toBe(true);
});
