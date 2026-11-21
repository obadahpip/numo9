import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * A-02-T16 — optional social sign-in behind the `auth.social_signin` flag. The sign-in page
 * reads allauth's configuration: providers listed (flag on) → "Continue with Google /
 * Microsoft"; none (flag off, the default) → no button. (The server side — flag off lists no
 * provider and refuses the redirect: backend/tests/test_auth_social_signin.py.)
 */
async function config(page: Page, providers: string[]) {
  await page.route("**/_allauth/browser/v1/config", (route) =>
    route.fulfill({
      json: {
        status: 200,
        data: {
          account: { login_methods: ["email"] },
          ...(providers.length
            ? { socialaccount: { providers: providers.map((id) => ({ id, name: id })) } }
            : {}),
        },
      },
    }),
  );
}

test("flag off: no social button", async ({ page }) => {
  await mockCsrf(page);
  await config(page, []);
  await page.goto("/login");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("button", { name: /Continue with/ })).toHaveCount(0);
});

test("flag on: Google and Microsoft buttons; a failed attempt explains itself", async ({
  page,
}) => {
  await mockCsrf(page);
  await config(page, ["google", "microsoft"]);
  await page.goto("/login?social=error");
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue with Microsoft" })).toBeVisible();
  await expect(page.getByText(/Signing in with that account didn't work/)).toBeVisible();
  await expectAccessible(page);
});
