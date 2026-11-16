import { expect, test } from "@playwright/test";

import { AUTH, mockCsrf } from "./auth-helpers";

/**
 * A-02-T15 — auth screens in French (fr-CA): with the locale cookie, the sign-in, sign-up,
 * reset and security screens show their French text (no English placeholder left), and the
 * missing-key gate (CI i18n job) passes for every auth key.
 */
test.use({ viewport: { width: 1280, height: 900 } });

test.beforeEach(async ({ context, baseURL }) => {
  await context.addCookies([{ name: "numo9_locale", value: "fr-CA", url: baseURL! }]);
});

test("sign-in, sign-up and reset screens are in French", async ({ page }) => {
  await mockCsrf(page);
  await page.route(`${AUTH}/auth/session`, (r) =>
    r.fulfill({
      status: 401,
      json: { status: 401, data: { flows: [] }, meta: { is_authenticated: false } },
    }),
  );
  await page.goto("/login");
  await expect(page.getByRole("heading", { level: 1, name: "Se connecter à Numo9" })).toBeVisible();
  await expect(page.getByLabel("Mot de passe")).toBeVisible();
  await expect(page.getByRole("link", { name: "Mot de passe oublié?" })).toBeVisible();

  await page.goto("/signup");
  await expect(
    page.getByRole("heading", { level: 1, name: "Créez votre compte Numo9" }),
  ).toBeVisible();
  await expect(page.getByText("Je suis comptable")).toBeVisible();

  await page.goto("/reset");
  await expect(
    page.getByRole("heading", { level: 1, name: "Réinitialiser votre mot de passe" }),
  ).toBeVisible();
});

test("security settings are in French", async ({ page }) => {
  await mockCsrf(page);
  await page.route(`${AUTH}/auth/sessions`, (r) => r.fulfill({ json: { status: 200, data: [] } }));
  await page.route(`${AUTH}/account/authenticators`, (r) =>
    r.fulfill({ json: { status: 200, data: [] } }),
  );
  await page.goto("/account/security");
  await expect(page.getByRole("heading", { level: 1, name: "Sécurité" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Activer l’authentification à deux facteurs" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { level: 2, name: "Où vous êtes connecté" }),
  ).toBeVisible();
});
