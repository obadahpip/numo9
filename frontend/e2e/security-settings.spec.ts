import { expect, test, type Page } from "@playwright/test";

import { AUTH, expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * A-02-T13 — Account → Security: 2FA, recovery codes, sessions list.
 * Acceptance: revoke works from the UI — "Sign out" on one session sends DELETE with its id and
 * the list shows what remains; "Sign out other sessions" sends every other id. Also: turning 2FA
 * on with the password confirmation (re-authentication), the recovery codes shown once, new
 * recovery codes; axe clean.
 */
const now = Date.now() / 1000;
const SESSIONS = [
  {
    id: 11,
    device: "Chrome on Windows",
    ip: "203.0.113.24",
    user_agent: "x",
    created_at: now - 3600,
    last_seen_at: now - 60,
    is_current: true,
  },
  {
    id: 12,
    device: "Safari on iPhone",
    ip: "198.51.100.7",
    user_agent: "y",
    created_at: now - 86400,
    last_seen_at: now - 7200,
    is_current: false,
  },
  {
    id: 13,
    device: "Firefox on Linux",
    ip: "192.0.2.5",
    user_agent: "z",
    created_at: now - 99999,
    last_seen_at: now - 9999,
    is_current: false,
  },
];

async function mockSecurity(page: Page, authenticators: unknown[] = []) {
  await mockCsrf(page);
  let sessions = [...SESSIONS];
  const deleted: number[][] = [];
  await page.route(`${AUTH}/auth/sessions`, (route) => {
    if (route.request().method() === "DELETE") {
      const ids = jsonBody(route).sessions as number[];
      deleted.push(ids);
      sessions = sessions.filter((s) => !ids.includes(s.id));
    }
    return route.fulfill({ json: { status: 200, data: sessions } });
  });
  await page.route(`${AUTH}/account/authenticators`, (r) =>
    r.fulfill({ json: { status: 200, data: authenticators } }),
  );
  return deleted;
}

test.use({ viewport: { width: 1280, height: 1000 } });

test("revoke one session, then the others, from the UI", async ({ page }) => {
  const deleted = await mockSecurity(page);
  await page.goto("/account/security");
  await expect(page.getByRole("heading", { level: 1, name: "Security" })).toBeVisible();
  await expect(page.locator("[data-session]")).toHaveCount(3);
  await expect(page.locator('[data-session="11"]')).toContainText("This device");
  await expect(page.locator('[data-session="11"]').getByRole("button")).toHaveCount(0);
  await expectAccessible(page);

  await page.getByRole("button", { name: "Sign out Safari on iPhone (198.51.100.7)" }).click();
  await expect(page.locator("[data-session]")).toHaveCount(2);
  await expect(page.locator("[data-security-status]")).toHaveText("1 session was signed out.");
  expect(deleted).toEqual([[12]]);

  await page.getByRole("button", { name: "Sign out other sessions" }).click();
  await expect(page.locator("[data-session]")).toHaveCount(1);
  expect(deleted).toEqual([[12], [13]]);
  await expect(page.getByRole("button", { name: "Sign out other sessions" })).toBeDisabled();
});

test("turn on 2FA after confirming the password; recovery codes shown once", async ({ page }) => {
  await mockSecurity(page);
  let reauthenticated = false;
  await page.route(`${AUTH}/auth/reauthenticate`, (route) => {
    reauthenticated = jsonBody(route).password === "correct horse battery 42";
    return route.fulfill({
      status: reauthenticated ? 200 : 400,
      json: { status: reauthenticated ? 200 : 400 },
    });
  });
  await page.route(`${AUTH}/account/authenticators/totp`, (route) => {
    if (!reauthenticated)
      return route.fulfill({
        status: 401,
        json: { status: 401, data: { flows: [{ id: "reauthenticate" }] } },
      });
    if (route.request().method() === "GET")
      return route.fulfill({
        status: 404,
        json: { status: 404, meta: { secret: "JBSWY3DPEHPK3PXP", qr_code: "" } },
      });
    const ok = jsonBody(route).code === "123456";
    return route.fulfill({
      status: ok ? 200 : 400,
      json: ok
        ? {
            status: 200,
            data: { type: "totp" },
            meta: { recovery_codes: ["k7m2p-x9qrt", "a1b2c-d3e4f"] },
          }
        : { status: 400, errors: [{ code: "incorrect_code", message: "Incorrect code." }] },
    });
  });
  await page.goto("/account/security");
  await expect(page.locator("[data-two-factor]")).toHaveText("Off");
  await page.getByRole("button", { name: "Turn on two-factor authentication" }).click();

  const confirm = page.getByRole("dialog", { name: "Confirm it's you" });
  await confirm.getByLabel("Password").fill("wrong password");
  await confirm.getByRole("button", { name: "Confirm" }).click();
  await expect(confirm.getByText("That password is incorrect.")).toBeVisible();
  await confirm.getByLabel("Password").fill("correct horse battery 42");
  await confirm.getByRole("button", { name: "Confirm" }).click();

  await expect(page.getByText("Key: JBSWY3DPEHPK3PXP")).toBeVisible();
  await page.getByLabel("Code from the app").fill("000000");
  await page.getByRole("button", { name: "Verify and turn on" }).click();
  await expect(page.getByText("That code didn't work.")).toBeVisible();
  await page.getByLabel("Code from the app").fill("123456");
  await page.getByRole("button", { name: "Verify and turn on" }).click();

  const codes = page.getByRole("dialog", { name: "Save your recovery codes now" });
  await expect(
    codes.getByRole("list", { name: "Recovery codes" }).getByRole("listitem"),
  ).toHaveText(["k7m2p-x9qrt", "a1b2c-d3e4f"]);
  await expectAccessible(page);
  await codes.getByRole("button", { name: "I've saved them" }).click();
  await expect(codes).toBeHidden();
});

test("make new recovery codes", async ({ page }) => {
  await mockSecurity(page, [
    { type: "totp", created_at: now, last_used_at: null },
    {
      type: "recovery_codes",
      created_at: now,
      last_used_at: null,
      total_code_count: 10,
      unused_code_count: 7,
    },
  ]);
  await page.route(`${AUTH}/account/authenticators/recovery-codes`, (route) =>
    route.fulfill({
      json: { status: 200, data: { type: "recovery_codes", unused_codes: ["zz9yy-xx8ww"] } },
    }),
  );
  await page.goto("/account/security");
  await expect(page.locator("[data-two-factor]")).toHaveText("On");
  await expect(page.getByText("7 of 10 codes unused.")).toBeVisible();
  await page.getByRole("button", { name: "Make new recovery codes" }).click();
  await expect(page.locator("[data-recovery-codes] li")).toHaveText(["zz9yy-xx8ww"]);
});
