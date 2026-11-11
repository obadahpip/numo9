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
 * A-02-T10 — sign-up screens: choose path → form → "open the link we emailed you" → verified
 * (flow F1). Acceptance target: F1 ≤ 90 s; here the scripted sign-up must take well under that.
 */
const PASSWORD = "correct horse battery 42";

async function fillAccountant(page: Page, email = "dana.lee@example.ca") {
  await page.getByLabel(/^Your name/).fill("Dana Lee");
  await page.getByLabel(/^Email/).fill(email);
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByLabel(/^Practice name/).fill("Maple Leaf Accounting");
}

for (const width of [360, 1280]) {
  test.describe(`sign-up at ${width} px`, () => {
    test.use({ viewport: { width, height: 900 } });

    test("accountant path: choose, fill, email sent — accessible at every step", async ({
      page,
    }) => {
      await mockCsrf(page);
      let sent: Record<string, unknown> = {};
      await page.route(`${AUTH}/auth/signup`, async (route) => {
        sent = jsonBody(route);
        await route.fulfill({
          status: 401,
          json: { status: 401, data: flows("verify_email"), meta: { is_authenticated: false } },
        });
      });
      const started = Date.now();
      await page.goto("/signup");
      await expect(page.getByRole("heading", { level: 1 })).toHaveText("Create your Numo9 account");
      await expectAccessible(page);
      await expectNoHorizontalScroll(page);

      await page.getByRole("button", { name: /I'm an accountant/ }).click();
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(
        "Create your free accountant account",
      );
      await expect(page.getByRole("heading", { level: 1 })).toBeFocused();
      await expectAccessible(page);
      await fillAccountant(page);
      await expect(page.getByText("Password strength: strong")).toBeVisible();
      await page.getByRole("button", { name: "Create account" }).click();

      await expect(page.getByRole("heading", { level: 1 })).toHaveText(
        "Open the link we emailed you",
      );
      await expect(page.getByRole("main").getByRole("status")).toContainText("dana.lee@example.ca");
      expect(Date.now() - started).toBeLessThan(90_000);
      expect(sent).toEqual({
        path: "accountant",
        name: "Dana Lee",
        email: "dana.lee@example.ca",
        password: PASSWORD,
        practice_name: "Maple Leaf Accounting",
        locale: "en-ca",
      });
      await expectAccessible(page);
      await expectNoHorizontalScroll(page);
    });
  });
}

test("organisation path from ?path=organisation asks for the business name", async ({ page }) => {
  await mockCsrf(page);
  let sent: Record<string, unknown> = {};
  await page.route(`${AUTH}/auth/signup`, async (route) => {
    sent = jsonBody(route);
    await route.fulfill({
      status: 401,
      json: { status: 401, data: flows("verify_email"), meta: {} },
    });
  });
  await page.goto("/signup?path=organisation");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Start your free 30-day trial");
  await page.getByLabel(/^Your name/).fill("Sam Roy");
  await page.getByLabel(/^Email/).fill("sam@refined.ca");
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByLabel(/^Business name/).fill("Refined Interiors Inc.");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Open the link we emailed you");
  expect(sent).toMatchObject({ path: "organisation", organisation_name: "Refined Interiors Inc." });
  expect(sent).not.toHaveProperty("practice_name");
});

test("client-side validation: summary, inline errors, focus on the first error", async ({
  page,
}) => {
  await mockCsrf(page);
  let calls = 0;
  await page.route(`${AUTH}/auth/signup`, (route) => {
    calls += 1;
    return route.abort();
  });
  await page.goto("/signup?path=accountant");
  // Untouched form: the error summary must appear and stay (form-kit fix, A-02-T10).
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForTimeout(500);

  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "There are 4 problems with this form",
  );
  await expect(page.getByLabel(/^Your name/)).toBeFocused();
  const summary = page.getByRole("main").getByRole("alert");
  await expect(summary.getByRole("link")).toHaveText([
    /^Your name: Enter your full name/,
    /^Email: Enter an email address/,
    /^Password: Use at least 12 characters/,
    /^Practice name: Enter your practice's name/,
  ]);
  await expect(page.getByLabel(/^Email/)).toHaveAttribute("aria-invalid", "true");
  // Fixing a field shrinks the summary.
  await page.getByLabel(/^Your name/).fill("Dana Lee");
  await page.getByLabel(/^Email/).focus();
  await expect(summary.getByRole("link")).toHaveCount(3);
  expect(calls).toBe(0);
  await expectAccessible(page);
});

test("server field errors land on their fields (breached password)", async ({ page }) => {
  await mockCsrf(page);
  await page.route(`${AUTH}/auth/signup`, (route) =>
    route.fulfill({
      status: 400,
      json: {
        status: 400,
        errors: [
          {
            message: "This password has appeared in a data breach. Choose a different one.",
            code: "password_breached",
            param: "password",
          },
        ],
      },
    }),
  );
  await page.goto("/signup?path=accountant");
  await fillAccountant(page);
  await page.getByRole("button", { name: "Create account" }).click();
  const password = page.getByLabel(/^Password/);
  await expect(password).toBeFocused();
  await expect(password).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByText("This password has appeared in a data breach.")).toBeVisible();
});

test("rate limit and offline answers explain what to do", async ({ page }) => {
  await mockCsrf(page);
  let answer: "limited" | "offline" = "limited";
  await page.route(`${AUTH}/auth/signup`, (route) =>
    answer === "limited"
      ? route.fulfill({ status: 429, headers: { "Retry-After": "600" }, json: { status: 429 } })
      : route.abort("internetdisconnected"),
  );
  await page.goto("/signup?path=accountant");
  await fillAccountant(page);
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "Too many attempts. For your security, wait 10 minutes before trying again.",
  );
  answer = "offline";
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "Numo9 couldn't be reached. Make sure you're online, then try again.",
  );
});

test("keyboard only: choose a path and sign up without a mouse", async ({ page }) => {
  await mockCsrf(page);
  await page.route(`${AUTH}/auth/signup`, (route) =>
    route.fulfill({ status: 401, json: { status: 401, data: flows("verify_email"), meta: {} } }),
  );
  await page.goto("/signup");
  await page.keyboard.press("Tab"); // first choice
  await expect(page.getByRole("button", { name: /I'm an accountant/ })).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Tab"); // "Choose a different account type"
  await page.keyboard.press("Tab");
  await page.keyboard.type("Dana Lee");
  await page.keyboard.press("Tab");
  await page.keyboard.type("dana.lee@example.ca");
  await page.keyboard.press("Tab");
  await page.keyboard.type(PASSWORD);
  await page.keyboard.press("Tab"); // Show password
  await page.keyboard.press("Tab");
  await page.keyboard.type("Maple Leaf Accounting");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Open the link we emailed you");
});

test.describe("verify link", () => {
  test("verified in the same browser: signed in, continue to Numo9", async ({ page }) => {
    await mockCsrf(page);
    let key: unknown;
    await page.route(`${AUTH}/auth/email/verify`, async (route) => {
      key = jsonBody(route).key;
      await route.fulfill({
        json: {
          status: 200,
          data: { user: { email: "dana.lee@example.ca" } },
          meta: { is_authenticated: true },
        },
      });
    });
    await page.goto("/verify/MQ:1tAbCd:xyz");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Your email is verified");
    await expect(page.getByRole("link", { name: "Continue to Numo9" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(key).toBe("MQ:1tAbCd:xyz");
    await expectAccessible(page);
  });

  test("verified in another browser: asked to sign in", async ({ page }) => {
    await mockCsrf(page);
    await page.route(`${AUTH}/auth/email/verify`, (route) =>
      route.fulfill({ status: 401, json: { status: 401, data: { flows: [] }, meta: {} } }),
    );
    await page.goto("/verify/abc");
    await expect(page.getByRole("main").getByRole("status")).toHaveText(
      "Sign in with your email and password to continue.",
    );
    await expect(page.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
  });

  test("expired or used link: explains and offers sign-in; posted once", async ({ page }) => {
    await mockCsrf(page);
    let posts = 0;
    await page.route(`${AUTH}/auth/email/verify`, (route) => {
      posts += 1;
      return route.fulfill({
        status: 400,
        json: {
          status: 400,
          errors: [
            { message: "Invalid or expired key.", code: "invalid_or_expired_key", param: "key" },
          ],
        },
      });
    });
    await page.goto("/verify/expired");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "This link doesn't work any more",
    );
    expect(posts).toBe(1);
    await expectAccessible(page);
  });

  test("server down: retry", async ({ page }) => {
    await mockCsrf(page);
    let attempt = 0;
    await page.route(`${AUTH}/auth/email/verify`, (route) => {
      attempt += 1;
      return attempt === 1
        ? route.fulfill({ status: 503, json: {} })
        : route.fulfill({ json: { status: 200, meta: { is_authenticated: true } } });
    });
    await page.goto("/verify/abc");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("We couldn't check your link");
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Your email is verified");
  });
});
