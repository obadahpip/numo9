import { expect, test, type Page } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";

/**
 * G-06-T11 — gap tests of the one tax settings page (teardown gaps):
 * - gap-39: every statutory number (BN, RT, RP, RC, QST, PST BC/SK, RST MB) on one page;
 * - gap-44: tax configuration on one page, not four — and a change is never silent: the
 *   history names who changed what;
 * - gap-03: "tax settings" links land on the card they are about, not on a generic page;
 * - gap-49 (the basis is set here only; the report chip links here) is in
 *   gap-46-49-54-55.spec.ts.
 */
const ORG = "acme";
const API = `**/api/v1/o/${ORG}`;
const PAGE = `/o/${ORG}/settings/registrations`;

async function mock(page: Page) {
  await mockCsrf(page);
  await page.route(`${API}/tax/registrations`, (r) => r.fulfill({ json: { results: [] } }));
  await page.route(`${API}/tax/settings`, (r) =>
    r.fulfill({
      json: {
        basis: "accrual",
        rounding_mode: "line",
        quick_method: false,
        quick_method_from: null,
        default_codes: {},
        restricted_itc_accounts: [],
        registered: false,
      },
    }),
  );
  await page.route(`${API}/tax/codes*`, (r) => r.fulfill({ json: { results: [] } }));
  await page.route(`${API}/audit/events*`, (r) =>
    r.fulfill({
      json: {
        results: [
          {
            id: "e1",
            at: "2026-06-01T15:00:00Z",
            action: "orgsettings.taxregistration.updated",
            action_label: "Tax registration changed",
            verb: "updated",
            actor: {
              kind: "user",
              label: "Dana Lee",
              user: { id: "u1", name: "Dana Lee", email: "dana@refined.ca" },
              impersonator: null,
            },
            record: {
              type: "orgsettings.TaxRegistration",
              type_label: "Tax registration",
              id: "r1",
              label: "GST/HST program account (RT) 123456782 RT 0001",
            },
            changes: [
              { field: "status", label: "Status", old: "active", new: "closed", masked: false },
            ],
            meta: {},
            ip: null,
            device: "",
            request_id: "",
            batch_id: null,
            is_batch_summary: false,
          },
        ],
        next: null,
        range: {
          from: "2026-01-01",
          to: "2026-12-31",
          default: true,
          time_zone: "America/Toronto",
        },
        viewer: { time_format: "12h", time_zone: "America/Toronto", locale: "en-ca" },
      },
    }),
  );
}

test.use({ viewport: { width: 1280, height: 1000 } });

test("gap-39: every statutory number is entered on the one page", async ({ page }) => {
  await mock(page);
  await page.goto(PAGE);
  await page.getByRole("button", { name: "Add registration" }).click();
  await page
    .locator('[data-registration="new"]')
    .getByRole("combobox", { name: "Registration" })
    .click();
  await expect(page.getByRole("option")).toHaveText([
    "Business Number (BN)",
    "GST/HST program account (RT)",
    "Payroll program account (RP)",
    "Corporate income tax program account (RC)",
    "Quebec QST number",
    "British Columbia PST number",
    "Saskatchewan PST number",
    "Manitoba RST number",
  ]);
});

test("gap-44: tax configuration is one page and a change is never silent", async ({ page }) => {
  await mock(page);
  await page.goto(PAGE);
  await expect(page.locator("[data-card]")).toHaveCount(5);
  await expect(
    page
      .locator("[data-card]")
      .evaluateAll((cards) => cards.map((c) => c.getAttribute("data-card"))),
  ).resolves.toEqual([
    "registrations",
    "tax-basis",
    "default-codes",
    "quick-method",
    "restricted-itc",
  ]);
  // The settings navigation has no other page for tax configuration than this one and the codes.
  const nav = page.getByRole("navigation", { name: "Settings sections" });
  await expect(nav.getByRole("link", { name: /tax/i })).toHaveText([
    "Tax registrations",
    "Tax codes",
  ]);
  // A registration that stops being active is in the history with who did it (Xero: silent).
  await page.locator("[data-tax-history]").click();
  const row = page.locator("[data-tax-history-list] > li").first();
  await expect(row).toContainText("Tax registration changed");
  await expect(row.locator("[data-who]")).toHaveText("Dana Lee");
  await expect(row).toContainText("Status");
});

test("gap-03: tax settings links open the card they are about", async ({ page }) => {
  await mock(page);
  await page.setViewportSize({ width: 1280, height: 500 });
  await page.goto(`/o/${ORG}/settings/tax-codes`);
  await page.locator("[data-tax-settings-link='default-codes']").click();
  await expect(page).toHaveURL(`${PAGE}#default-codes`);
  await expect(page.locator("[data-card='default-codes']")).toBeInViewport();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Tax registrations and settings",
  );
});
