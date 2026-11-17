import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * U-06-T11 — impersonation UI: start modal (reason, time limit), the red bar with its countdown
 * on every page, "End session". Fixtures in the API's shape (backend/numo9/platform/api.py,
 * tested against the real middleware in backend/tests/test_platform_impersonation_auth.py).
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const IMP = "**/api/v1/platform/impersonation";

const detail = {
  id: ORG,
  name: "Maple Leaf Supply Ltd.",
  status: "active",
  is_demo: false,
  province: "ON",
  time_zone: "America/Toronto",
  created_at: "2026-10-02T14:00:00Z",
  subscription: null,
  timeline: [],
  users: [{ id: "u-1", name: "Dana Lee", email: "dana@maple.ca", role: "owner", last_login: null }],
  practices: [],
  recent_events: [],
};

function session() {
  const now = Date.now();
  return {
    id: "s-1",
    actor: { id: "staff-1", name: "Priya Shah", email: "priya@numo9.ca" },
    user: { id: "u-1", name: "Dana Lee", email: "dana@maple.ca" },
    organisation: { id: ORG, name: "Maple Leaf Supply Ltd." },
    reason: "Ticket #42",
    started_at: new Date(now).toISOString(),
    expires_at: new Date(now + 30 * 60_000).toISOString(),
    ended_at: null,
    end_reason: "",
  };
}

async function mockSession(page: Page, open: { value: boolean }) {
  await page.route(`${IMP}/current`, (r) =>
    r.fulfill({ json: { session: open.value ? session() : null, ended: null } }),
  );
  await page.route(`${IMP}/end`, (r) => {
    open.value = false;
    return r.fulfill({ json: { session: null, ended: { ...session(), end_reason: "ended" } } });
  });
}

test("start a session from the organisation, see the red bar on every page, end it", async ({
  page,
}) => {
  await mockCsrf(page);
  const open = { value: false };
  await mockSession(page, open);
  await page.route(`**/api/v1/platform/organisations/${ORG}`, (r) => r.fulfill({ json: detail }));
  let started: Record<string, unknown> | null = null;
  await page.route(IMP, (r) => {
    started = jsonBody(r);
    open.value = true;
    return r.fulfill({ status: 201, json: session() });
  });

  await page.goto(`/console/organisations/${ORG}`);
  await page.getByRole("button", { name: "Sign in as Dana Lee" }).click();
  const dialog = page.getByRole("dialog", { name: "Sign in as Dana Lee" });
  await dialog.getByLabel("Reason").fill("Ticket #42");
  await dialog.getByLabel("Time limit").selectOption("15");
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Start session" }).click();
  await expect(page).toHaveURL(new RegExp(`/o/${ORG}/home$`));
  expect(started).toEqual({ organisation: ORG, user: "u-1", reason: "Ticket #42", minutes: 15 });

  for (const url of [`/o/${ORG}/home`, `/o/${ORG}/contacts`, "/console"]) {
    await page.goto(url);
    const bar = page.getByRole("region", { name: "Support session" });
    await expect(bar).toContainText("You're signed in as Dana Lee in Maple Leaf Supply Ltd.");
    await expect(bar.getByRole("timer")).toContainText(/\d\d:\d\d left/);
  }
  await page
    .getByRole("region", { name: "Support session" })
    .getByRole("button", { name: "End session" })
    .click();
  await expect(page).toHaveURL(new RegExp(`/console/organisations/${ORG}$`));
  await expect(page.getByRole("region", { name: "Support session" })).toHaveCount(0);
});
