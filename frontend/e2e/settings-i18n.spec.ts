import { expect, test } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";

/**
 * A-05-T15 — i18n keys + Canadian terminology: the settings pages of A-05 in French (fr-CA) —
 * Général, Inscriptions fiscales, Dates de verrouillage — with Canadian terms (NE, TPS/TVH,
 * province, code postal, courriel); the glossary lint and missing-key gate run in CI.
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
test.use({ viewport: { width: 1280, height: 1000 } });

test.beforeEach(async ({ context, baseURL, page }) => {
  await context.addCookies([{ name: "numo9_locale", value: "fr-CA", url: baseURL! }]);
  await mockCsrf(page);
});

test("settings pages in French", async ({ page }) => {
  await page.route(`**/api/v1/o/${ORG}/settings`, (r) =>
    r.fulfill({
      json: {
        display_name: "Raffinés",
        legal_name: "",
        industry: "",
        structure: "",
        mailing_line1: "",
        mailing_line2: "",
        mailing_city: "",
        mailing_province: "QC",
        mailing_postal_code: "",
        phone: "",
        email: "",
        website: "",
        fye_month: 12,
        fye_day: 31,
        base_currency: "CAD",
        time_zone: "America/Toronto",
      },
    }),
  );
  await page.goto(`/o/${ORG}/settings/general`);
  await expect(page.getByRole("heading", { level: 1, name: "Général" })).toBeVisible();
  await expect(page.getByText("Devise de base : CAD (non modifiable)")).toBeVisible();
  await expect(page.getByLabel("Code postal")).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Province ou territoire" })).toContainText(
    "Québec",
  );
  const nav = page.getByRole("navigation", { name: "Sections des paramètres" });
  await expect(nav.getByRole("link", { name: "Inscriptions fiscales" })).toBeVisible();

  await page.route(`**/api/v1/o/${ORG}/settings/registrations`, (r) => r.fulfill({ json: [] }));
  await page.goto(`/o/${ORG}/settings/registrations`);
  await expect(
    page.getByRole("heading", { level: 1, name: "Inscriptions fiscales" }),
  ).toBeVisible();
  await expect(page.getByText(/numéro d’entreprise \(NE\).*TPS\/TVH/)).toBeVisible();

  await page.route(`**/api/v1/o/${ORG}/settings/lock-dates`, (r) =>
    r.fulfill({
      json: [
        {
          module: "gl",
          module_label: "Grand livre",
          advisers_only: { date: null, reason: "", updated_at: null },
          everyone: { date: null, reason: "", updated_at: null },
        },
      ],
    }),
  );
  await page.goto(`/o/${ORG}/settings/lock-dates`);
  await expect(
    page.getByRole("heading", { level: 1, name: "Dates de verrouillage" }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Tout le monde sauf les conseillers" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Non verrouillé — Grand livre, Tout le monde", exact: true }),
  ).toBeVisible();
});
