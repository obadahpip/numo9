import { expect, test, type Page } from "@playwright/test";

import {
  AUTH,
  expectAccessible,
  expectNoHorizontalScroll,
  flows,
  jsonBody,
  mockCsrf,
} from "./auth-helpers";

/**
 * A-02-T11 — login, 2FA challenge and password reset screens; CodeInput is paste-aware.
 * Acceptance: keyboard-only completion; axe 0 serious/critical on every screen.
 */
const EMAIL = "dana.lee@example.ca";
const PASSWORD = "correct horse battery 42";
const signedIn = {
  status: 200,
  data: { user: { email: EMAIL } },
  meta: { is_authenticated: true },
};

interface Reply {
  status?: number;
  json: unknown;
  headers?: Record<string, string>;
}

async function mockLogin(page: Page, answer: (body: Record<string, unknown>) => Reply) {
  await page.route(`${AUTH}/auth/login`, async (route) => {
    const reply = answer(jsonBody(route));
    await route.fulfill(reply);
  });
}

const mfaPending = {
  status: 401,
  json: { status: 401, data: flows("mfa_authenticate"), meta: { is_authenticated: false } },
};

test.describe("login", () => {
  for (const width of [360, 1280]) {
    test(`password only: signs in and goes to next (${width} px)`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await mockCsrf(page);
      let sent: Record<string, unknown> = {};
      await mockLogin(page, (body) => {
        sent = body;
        return { status: 200, json: signedIn };
      });
      await page.goto("/login?next=/o/acme/contacts");
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("Sign in to Numo9");
      await expectAccessible(page);
      await expectNoHorizontalScroll(page);
      await page.getByLabel(/^Email/).fill(EMAIL);
      await page.getByLabel(/^Password/).fill(PASSWORD);
      await page.getByRole("button", { name: "Sign in", exact: true }).click();
      await expect(page).toHaveURL("/o/acme/contacts");
      expect(sent).toEqual({ email: EMAIL, password: PASSWORD });
    });
  }

  test("an outside next is ignored (no open redirect)", async ({ page }) => {
    await mockCsrf(page);
    await mockLogin(page, () => ({ status: 200, json: signedIn }));
    await page.goto("/login?next=//evil.example/steal");
    await page.getByLabel(/^Email/).fill(EMAIL);
    await page.getByLabel(/^Password/).fill(PASSWORD);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL("/");
  });

  test("wrong email or password: one message for both", async ({ page }) => {
    await mockCsrf(page);
    await mockLogin(page, () => ({
      status: 401,
      json: {
        status: 401,
        errors: [
          {
            message: "The email address and/or password you specified are not correct.",
            code: "email_password_mismatch",
            param: "password",
          },
        ],
      },
    }));
    await page.goto("/login");
    await page.getByLabel(/^Email/).fill(EMAIL);
    await page.getByLabel(/^Password/).fill("not my password");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("main").getByRole("alert")).toHaveText(
      "The email or password is incorrect. Try again, or reset your password if you've forgotten it.",
    );
    await expectAccessible(page);
  });

  test("locked account says for how long and offers the reset", async ({ page }) => {
    await mockCsrf(page);
    await mockLogin(page, () => ({
      status: 429,
      headers: { "Retry-After": "840" },
      json: { status: 429 },
    }));
    await page.goto("/login");
    await page.getByLabel(/^Email/).fill(EMAIL);
    await page.getByLabel(/^Password/).fill(PASSWORD);
    await page.keyboard.press("Enter");
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
      "this account is locked for 14 minutes",
    );
    await expect(page.getByRole("link", { name: "Forgot your password?" })).toHaveAttribute(
      "href",
      "/reset",
    );
  });

  test("unverified email: told to verify first", async ({ page }) => {
    await mockCsrf(page);
    await mockLogin(page, () => ({
      status: 401,
      json: { status: 401, data: flows("verify_email"), meta: {} },
    }));
    await page.goto("/login");
    await page.getByLabel(/^Email/).fill(EMAIL);
    await page.getByLabel(/^Password/).fill(PASSWORD);
    await page.keyboard.press("Enter");
    await expect(page.getByRole("main").getByRole("status")).toContainText(
      `Verify your email address first. We've emailed a new link to ${EMAIL}`,
    );
  });

  test("after a reset the login page confirms the change", async ({ page }) => {
    await page.goto("/login?reset=done");
    await expect(page.getByRole("main").getByRole("status")).toContainText(
      "Your password was changed",
    );
  });
});

test.describe("2FA challenge", () => {
  test("keyboard only: password, wrong code, right code, remember device", async ({ page }) => {
    await mockCsrf(page);
    await mockLogin(page, () => mfaPending);
    const codes: unknown[] = [];
    await page.route(`${AUTH}/auth/2fa/authenticate`, async (route) => {
      const { code } = jsonBody(route);
      codes.push(code);
      await route.fulfill(
        code === "246810"
          ? { status: 401, json: { status: 401, data: flows("mfa_trust"), meta: {} } }
          : {
              status: 400,
              json: {
                status: 400,
                errors: [{ message: "Incorrect code.", code: "incorrect_code", param: "code" }],
              },
            },
      );
    });
    let trust: unknown;
    await page.route(`${AUTH}/auth/2fa/trust`, async (route) => {
      trust = jsonBody(route).trust;
      await route.fulfill({ json: signedIn });
    });

    await page.goto("/login?next=/o/acme/home");
    await page.keyboard.press("Tab");
    await expect(page.getByLabel(/^Email/)).toBeFocused();
    await page.keyboard.type(EMAIL);
    await page.keyboard.press("Tab");
    await page.keyboard.type(PASSWORD);
    await page.keyboard.press("Enter");

    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Enter your authentication code",
    );
    const first = page.getByRole("textbox", { name: "Digit 1 of 6" });
    await expect(first).toBeFocused();
    await expectAccessible(page);
    await page.keyboard.type("111111"); // complete → submits by itself
    await expect(page.getByRole("main").getByRole("alert")).toContainText("That code didn't work.");
    await expect(first).toBeFocused();
    await expect(first).toHaveValue("");
    await expectAccessible(page);

    // Remember this device: Tab through the boxes to the checkbox, Space, back to the code.
    for (let i = 0; i < 6; i++) await page.keyboard.press("Tab");
    await expect(
      page.getByRole("checkbox", { name: "Remember this device for 30 days" }),
    ).toBeFocused();
    await page.keyboard.press("Space");
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Home");
    await page.keyboard.type("246810");
    await expect(page).toHaveURL("/o/acme/home");
    expect(codes).toEqual(["111111", "246810"]);
    expect(trust).toBe(true);
  });

  test("pasting the code fills every box and submits", async ({ page, context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await mockCsrf(page);
    await mockLogin(page, () => mfaPending);
    let code: unknown;
    await page.route(`${AUTH}/auth/2fa/authenticate`, async (route) => {
      code = jsonBody(route).code;
      await route.fulfill({ json: signedIn });
    });
    await page.goto("/login");
    await page.getByLabel(/^Email/).fill(EMAIL);
    await page.getByLabel(/^Password/).fill(PASSWORD);
    await page.keyboard.press("Enter");
    const third = page.getByRole("textbox", { name: "Digit 3 of 6" });
    await third.focus();
    await page.evaluate(() => navigator.clipboard.writeText("Your Numo9 code: 482 913"));
    await page.keyboard.press("ControlOrMeta+V");
    await expect(page).toHaveURL("/");
    expect(code).toBe("482913");
  });

  test("recovery code instead of the app; a used one is explained", async ({ page }) => {
    await mockCsrf(page);
    await mockLogin(page, () => mfaPending);
    let attempt = 0;
    await page.route(`${AUTH}/auth/2fa/authenticate`, async (route) => {
      attempt += 1;
      const { code } = jsonBody(route);
      expect(code).toBe(attempt === 1 ? "k7m2p-x9qrt" : "w7jhr-wftbs");
      await route.fulfill(
        attempt === 1
          ? {
              status: 400,
              json: {
                status: 400,
                errors: [{ message: "Incorrect code.", code: "incorrect_code", param: "code" }],
              },
            }
          : { json: signedIn },
      );
    });
    await page.goto("/login");
    await page.getByLabel(/^Email/).fill(EMAIL);
    await page.getByLabel(/^Password/).fill(PASSWORD);
    await page.keyboard.press("Enter");
    await page.getByRole("button", { name: "Use a recovery code instead" }).click();
    const field = page.getByLabel("Recovery code");
    await expect(field).toBeFocused();
    await field.fill(" k7m2p-x9qrt ");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("main").getByRole("alert")).toContainText("each code works once");
    await expectAccessible(page);
    await field.fill("w7jhr-wftbs");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL("/");
  });

  test("timed-out sign-in sends the user back to sign in", async ({ page }) => {
    await mockCsrf(page);
    await mockLogin(page, () => mfaPending);
    await page.route(`${AUTH}/auth/2fa/authenticate`, (route) =>
      route.fulfill({
        status: 401,
        json: { status: 401, data: { flows: [{ id: "login" }] }, meta: {} },
      }),
    );
    await page.goto("/login");
    await page.getByLabel(/^Email/).fill(EMAIL);
    await page.getByLabel(/^Password/).fill(PASSWORD);
    await page.keyboard.press("Enter");
    await page.getByRole("textbox", { name: "Digit 1 of 6" }).focus();
    await page.keyboard.type("123456");
    await expect(page.getByRole("main").getByRole("alert")).toContainText("Your sign-in timed out");
    await expect(
      page.getByRole("main").getByRole("alert").getByRole("link", { name: "Sign in" }),
    ).toHaveAttribute("href", "/login");
  });

  test("/2fa without a waiting sign-in explains; with one shows the code step", async ({
    page,
  }) => {
    let pending = false;
    await page.route(`${AUTH}/auth/session`, (route) =>
      route.fulfill({
        status: 401,
        json: { status: 401, data: pending ? flows("mfa_authenticate") : { flows: [] }, meta: {} },
      }),
    );
    await page.goto("/2fa");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Sign in first");
    await expectAccessible(page);
    pending = true;
    await page.goto("/2fa");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Enter your authentication code",
    );
  });
});

test.describe("password reset", () => {
  test("request: the same confirmation for any address", async ({ page }) => {
    await mockCsrf(page);
    let sent: unknown;
    await page.route(`${AUTH}/auth/password/request`, async (route) => {
      sent = jsonBody(route).email;
      await route.fulfill({ json: { status: 200 } });
    });
    await page.goto("/login");
    await page.getByRole("link", { name: "Forgot your password?" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Reset your password");
    await expectAccessible(page);
    await page.getByLabel(/^Email/).fill("nobody@example.ca");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Look for our email");
    await expect(page.getByRole("main").getByRole("status")).toContainText(
      "If nobody@example.ca has a Numo9 account, a reset link is on its way. It works once, for 1 hour.",
    );
    expect(sent).toBe("nobody@example.ca");
    await expectAccessible(page);
  });

  test("new password: checks, server rule error, success → sign in", async ({ page }) => {
    await mockCsrf(page);
    await page.route(`${AUTH}/auth/password/reset`, async (route) => {
      const request = route.request();
      if (request.method() === "GET") {
        expect(request.headers()["x-password-reset-key"]).toBe("4-abc:key");
        return route.fulfill({ json: { status: 200, data: { user: { email: EMAIL } } } });
      }
      const { password, key } = jsonBody(route);
      expect(key).toBe("4-abc:key");
      if (password === "password1234")
        return route.fulfill({
          status: 400,
          json: {
            status: 400,
            errors: [
              {
                message: "This password is too common.",
                code: "password_too_common",
                param: "password",
              },
            ],
          },
        });
      return route.fulfill({
        status: 401,
        json: { status: 401, data: { flows: [{ id: "login" }] }, meta: {} },
      });
    });
    await page.goto("/reset/4-abc%3Akey");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Choose a new password");
    await expect(page.getByText(`For ${EMAIL}.`)).toBeVisible();
    await expectAccessible(page);

    await page.getByLabel(/^New password/).fill(PASSWORD);
    await page.getByLabel(/^Type the new password again/).fill("something else entirely");
    await page.getByLabel(/^New password/).focus();
    await page.getByRole("button", { name: "Save new password" }).click();
    await expect(page.getByText("The two passwords are different.").first()).toBeVisible();

    await page.getByLabel(/^New password/).fill("password1234");
    await page.getByLabel(/^Type the new password again/).fill("password1234");
    await page.keyboard.press("Enter");
    await expect(page.getByText("This password is too common.")).toBeVisible();
    await expect(page.getByLabel(/^New password/)).toBeFocused();

    await page.getByLabel(/^New password/).fill(PASSWORD);
    await page.getByLabel(/^Type the new password again/).fill(PASSWORD);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL("/login?reset=done");
  });

  test("expired or used link says so before any typing", async ({ page }) => {
    await page.route(`${AUTH}/auth/password/reset`, (route) =>
      route.fulfill({
        status: 400,
        json: {
          status: 400,
          errors: [{ message: "x", code: "invalid_password_reset", param: "key" }],
        },
      }),
    );
    await page.goto("/reset/used-key");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "This reset link doesn't work any more",
    );
    await expect(page.getByRole("link", { name: "Request a new link" })).toHaveAttribute(
      "href",
      "/reset",
    );
    await expectAccessible(page);
  });
});
