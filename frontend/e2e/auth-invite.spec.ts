import { expect, test, type Page } from "@playwright/test";

import {
  AUTH,
  expectAccessible,
  expectNoHorizontalScroll,
  jsonBody,
  mockCsrf,
} from "./auth-helpers";

/**
 * A-02-T12 — invitation accept screen. Acceptance: every state renders — signed out, signed in
 * as the invited account, wrong account (switch), accepted, expired, already used, withdrawn,
 * invalid — each accessible. API shapes: docs/architecture/authentication.md § Invitations.
 */
const TOKEN = "test-invitation-token-from-the-email-link";
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";

const INVITATION = {
  id: "1d2e3f40-5a6b-4c7d-8e9f-0a1b2c3d4e5f",
  kind: "organisation_user",
  email: "sam@refined.ca",
  role: "purchasing",
  status: "pending",
  expires_at: "2026-11-18T15:00:00Z",
  target_name: "Refined Interiors Inc.",
  target_id: ORG,
  inviter_name: "Dana Lee",
};

const SIGNED_OUT = {
  status: 401,
  json: { status: 401, data: { flows: [{ id: "login" }] }, meta: { is_authenticated: false } },
};
const signedInAs = (email: string) => ({
  status: 200,
  json: { status: 200, data: { user: { email } }, meta: { is_authenticated: true } },
});

async function mockInvite(
  page: Page,
  {
    preview = { status: 200, json: INVITATION as unknown },
    session = SIGNED_OUT as { status: number; json: unknown },
  }: {
    preview?: { status: number; json: unknown };
    session?: { status: number; json: unknown };
  } = {},
) {
  await mockCsrf(page);
  const seen: unknown[] = [];
  await page.route("**/api/v1/invitations/preview", async (route) => {
    seen.push(jsonBody(route).token);
    await route.fulfill(preview);
  });
  await page.route(`${AUTH}/auth/session`, (route) => route.fulfill(session));
  return seen;
}

test("signed out: what, who, role, expiry; sign in returns here", async ({ page }) => {
  const tokens = await mockInvite(page);
  await page.goto(`/invite/${TOKEN}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "You're invited to Refined Interiors Inc.",
  );
  await expect(
    page.getByText("Dana Lee invited you to join Refined Interiors Inc. as Purchasing."),
  ).toBeVisible();
  await expect(page.getByText("Invitation for sam@refined.ca · expires 18 Nov 2026")).toBeVisible();
  await expect(page.getByRole("link", { name: "Sign in to accept" })).toHaveAttribute(
    "href",
    `/login?next=${encodeURIComponent(`/invite/${TOKEN}`)}`,
  );
  await expect(page.getByText("Create your account with sam@refined.ca")).toBeVisible();
  expect(tokens).toEqual([TOKEN]); // in the body, never in an API URL
  await expectAccessible(page);
});

for (const width of [360, 1280]) {
  test(`signed in as the invited account: accept → open the organisation (${width} px)`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockInvite(page, { session: signedInAs("SAM@refined.ca") });
    let accepted: Record<string, unknown> = {};
    await page.route("**/api/v1/invitations/accept", async (route) => {
      accepted = jsonBody(route);
      await route.fulfill({ json: { ...INVITATION, status: "accepted" } });
    });
    await page.goto(`/invite/${TOKEN}`);
    await expect(page.getByText("You're signed in as SAM@refined.ca.")).toBeVisible();
    await expectAccessible(page);
    await expectNoHorizontalScroll(page);
    await page.getByRole("button", { name: "Accept invitation" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "You've joined Refined Interiors Inc.",
    );
    await expect(page.getByRole("link", { name: "Open Refined Interiors Inc." })).toHaveAttribute(
      "href",
      `/o/${ORG}/home`,
    );
    expect(accepted).toEqual({ token: TOKEN });
    await expectAccessible(page);
  });
}

test("wrong account: names both addresses; sign out and continue", async ({ page }) => {
  let signedIn = true;
  await mockCsrf(page);
  await page.route("**/api/v1/invitations/preview", (route) => route.fulfill({ json: INVITATION }));
  let loggedOut = false;
  await page.route(`${AUTH}/auth/session`, async (route) => {
    if (route.request().method() === "DELETE") {
      jsonBody(route); // CSRF header checked
      signedIn = false;
      loggedOut = true;
      return route.fulfill(SIGNED_OUT);
    }
    return route.fulfill(signedIn ? signedInAs("dana@mapleleaf.ca") : SIGNED_OUT);
  });
  await page.goto(`/invite/${TOKEN}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "This invitation is for another account",
  );
  await expect(page.getByRole("main").getByRole("status")).toHaveText(
    "It was sent to sam@refined.ca, but you're signed in as dana@mapleleaf.ca. Sign out, then sign in or create an account with sam@refined.ca.",
  );
  await expectAccessible(page);
  await page.getByRole("button", { name: "Sign out and continue" }).click();
  await expect(page.getByRole("link", { name: "Sign in to accept" })).toBeVisible();
  expect(loggedOut).toBe(true);
});

const DEAD: [string, number, string, string, string][] = [
  [
    "expired",
    410,
    "invitation.expired",
    "This invitation has expired",
    "This invitation expired on Nov. 10, 2026. Ask the person who sent it to resend it.",
  ],
  [
    "used",
    410,
    "invitation.used",
    "This invitation has already been accepted",
    "This invitation has already been accepted. Sign in to open it.",
  ],
  [
    "revoked",
    410,
    "invitation.revoked",
    "This invitation was withdrawn",
    "This invitation was withdrawn by the person who sent it. Ask them for a new one.",
  ],
  [
    "invalid",
    404,
    "invitation.invalid",
    "This invitation link doesn't work",
    "This invitation link isn't valid. Make sure you copied the whole link from the email.",
  ],
];

for (const [state, status, code, title, detail] of DEAD) {
  test(`${state} link: own heading, the server's explanation, a way on`, async ({ page }) => {
    await mockInvite(page, { preview: { status, json: { detail, code } } });
    await page.goto(`/invite/${TOKEN}`);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
    await expect(page.getByText(detail)).toBeVisible();
    await expect(page.locator("[data-invite-state]")).toHaveAttribute("data-invite-state", state);
    await expect(
      page.getByRole("link", { name: state === "used" ? "Sign in" : "Go to Home" }),
    ).toBeVisible();
    await expectAccessible(page);
  });
}

test("used between opening and accepting: the accept answer switches to the used state", async ({
  page,
}) => {
  await mockInvite(page, { session: signedInAs("sam@refined.ca") });
  await page.route("**/api/v1/invitations/accept", (route) =>
    route.fulfill({
      status: 410,
      json: {
        detail: "This invitation has already been accepted. Sign in to open it.",
        code: "invitation.used",
      },
    }),
  );
  await page.goto(`/invite/${TOKEN}`);
  await page.getByRole("button", { name: "Accept invitation" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "This invitation has already been accepted",
  );
});

test("accountant in several practices picks the practice", async ({ page }) => {
  await mockInvite(page, {
    preview: {
      status: 200,
      json: { ...INVITATION, kind: "organisation_accountant", role: "bookkeeping" },
    },
    session: signedInAs("sam@refined.ca"),
  });
  await page.route("**/api/v1/me/organisations", (route) =>
    route.fulfill({
      json: [
        {
          id: "0b1c2d3e-4f50-4617-8899-aabbccddeeff",
          name: "Northern Lights Bakery Inc.",
          status: "active",
          time_zone: "America/Toronto",
          membership: null,
          via_practices: [
            {
              practice_id: "p-2",
              practice_name: "Profitex Tax",
              practice_role: "accountant",
              assignment_role: "tax",
              assigned_staff: true,
            },
            {
              practice_id: "p-1",
              practice_name: "Profitex",
              practice_role: "accountant",
              assignment_role: "full_service",
              assigned_staff: true,
            },
          ],
        },
      ],
    }),
  );
  const bodies: Record<string, unknown>[] = [];
  await page.route("**/api/v1/invitations/accept", async (route) => {
    const body = jsonBody(route);
    bodies.push(body);
    await route.fulfill(
      body.practice
        ? { json: { ...INVITATION, status: "accepted" } }
        : {
            status: 400,
            json: {
              detail:
                "You belong to more than one practice. Choose the practice that will serve this client.",
              code: "invitation.choose_practice",
            },
          },
    );
  });
  await page.goto(`/invite/${TOKEN}`);
  await expect(
    page.getByText(
      "Dana Lee invited you and your practice to look after Refined Interiors Inc. (bookkeeping).",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Accept invitation" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "You belong to more than one practice.",
  );
  await page.getByRole("combobox", { name: "Practice that will serve this client" }).click();
  await expect(page.getByRole("option")).toHaveText(["Profitex", "Profitex Tax"]);
  await page.getByRole("option", { name: "Profitex Tax" }).click();
  await page.getByRole("button", { name: "Accept invitation" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "You've joined Refined Interiors Inc.",
  );
  expect(bodies.at(-1)).toEqual({ token: TOKEN, practice: "p-2" });
});

test("server unreachable: retry", async ({ page }) => {
  let attempt = 0;
  await mockCsrf(page);
  await page.route(`${AUTH}/auth/session`, (route) => route.fulfill(SIGNED_OUT));
  await page.route("**/api/v1/invitations/preview", (route) => {
    attempt += 1;
    return attempt === 1
      ? route.abort("internetdisconnected")
      : route.fulfill({ json: INVITATION });
  });
  await page.goto(`/invite/${TOKEN}`);
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Numo9 couldn't be reached.",
  );
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "You're invited to Refined Interiors Inc.",
  );
});
