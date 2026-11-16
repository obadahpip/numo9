import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * A-07-T09 — Notification centre UI: bell with the unread count, drawer grouped by day with
 * mark-read / mark-all, preferences page. Acceptance: the a11y live region announces new
 * notifications; axe clean (drawer and preferences page).
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}/notifications`;

const now = new Date();
const yesterday = new Date(now.getTime() - 86_400_000);
const items = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    category: "jobs",
    category_label: "Background jobs",
    title: "Import contacts finished",
    body: "512 rows imported.",
    title_key: "notifications.job.finished",
    link: `/o/${ORG}/contacts`,
    read: false,
    read_at: null,
    created_at: now.toISOString(),
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    category: "documents",
    category_label: "Documents",
    title: "invoice.pdf was blocked",
    body: "The virus scan found a threat.",
    title_key: "notifications.document.quarantined",
    link: "",
    read: true,
    read_at: yesterday.toISOString(),
    created_at: yesterday.toISOString(),
  },
];

async function mockCentre(page: Page, counts: number[]) {
  await mockCsrf(page);
  let call = 0;
  await page.route(`${API}/unread-count`, (r) =>
    r.fulfill({ json: { unread_count: counts[Math.min(call++, counts.length - 1)] } }),
  );
  const marked: string[] = [];
  await page.route(API, (r) =>
    r.fulfill({ json: { results: items, unread_count: 1, next: null } }),
  );
  await page.route(`${API}/*/read`, (r) => {
    marked.push(r.request().url());
    return r.fulfill({ json: { ...items[0], read: true } });
  });
  await page.route(`${API}/read-all`, (r) => r.fulfill({ json: { marked: 1, unread_count: 0 } }));
  return marked;
}

test.use({ viewport: { width: 1280, height: 900 } });

test("bell shows the unread count; drawer groups by day and marks read", async ({ page }) => {
  const marked = await mockCentre(page, [1]);
  await page.goto(`/o/${ORG}/settings/package-features`);
  const bell = page.getByRole("button", { name: "Notifications, 1 unread" });
  await expect(bell).toBeVisible();
  await bell.click();

  const drawer = page.getByRole("dialog", { name: "Notifications" });
  await expect(drawer.getByRole("heading", { level: 3, name: "Today" })).toBeVisible();
  await expect(drawer.getByRole("heading", { level: 3, name: "Yesterday" })).toBeVisible();
  await expect(drawer.locator('[data-read="false"]')).toHaveCount(1);
  await expect(drawer.getByText("Unread:")).toHaveCount(1);
  await expectAccessible(page);

  await drawer.getByRole("button", { name: "Mark as read: Import contacts finished" }).click();
  await expect(drawer.locator('[data-read="false"]')).toHaveCount(0);
  await expect.poll(() => marked[0]).toContain("11111111-1111-4111-8111-111111111111/read");
  await expect(drawer.getByRole("link", { name: "Notification settings" })).toHaveAttribute(
    "href",
    `/o/${ORG}/settings/notifications`,
  );
});

test("mark all as read", async ({ page }) => {
  await mockCentre(page, [1, 0]);
  await page.goto(`/o/${ORG}/settings/package-features`);
  await page.getByRole("button", { name: "Notifications, 1 unread" }).click();
  const drawer = page.getByRole("dialog", { name: "Notifications" });
  await drawer.getByRole("button", { name: "Mark all as read" }).click();
  await expect(drawer.locator('[data-read="false"]')).toHaveCount(0);
  await expect(drawer.getByRole("button", { name: "Mark all as read" })).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Notifications", exact: true })).toBeVisible();
});

test("the live region announces new notifications", async ({ page }) => {
  await mockCentre(page, [1, 3]);
  await page.clock.install();
  await page.goto(`/o/${ORG}/settings/package-features`);
  const live = page.locator("[data-notifications-live]");
  await expect(page.getByRole("button", { name: "Notifications, 1 unread" })).toBeVisible();
  await expect(live).toHaveAttribute("aria-live", "polite");
  await expect(live).toHaveText(""); // nothing on page load
  await page.clock.runFor(31_000);
  await expect(page.getByRole("button", { name: "Notifications, 3 unread" })).toBeVisible();
  await expect(live).toHaveText("You have 3 unread notifications.");
});

test("preferences: switches save, security is locked", async ({ page }) => {
  await mockCentre(page, [0]);
  const categories = [
    ["system", "Account and system", true, true, false],
    ["security", "Security", true, true, true],
    ["jobs", "Background jobs", true, false, false],
  ] as const;
  const results = categories.map(([category, category_label, in_app, email, locked]) => ({
    category,
    category_label,
    in_app,
    email,
    locked,
    is_default: true,
  }));
  const sent: Record<string, unknown>[] = [];
  await page.route(`${API}/preferences`, (r) => {
    if (r.request().method() === "PATCH") {
      const body = jsonBody(r);
      sent.push(body);
      return r.fulfill({ json: { ...results[2], ...body, is_default: false } });
    }
    return r.fulfill({ json: { results } });
  });
  await page.goto(`/o/${ORG}/settings/notifications`);
  await expect(page.getByRole("heading", { level: 1, name: "Notifications" })).toBeVisible();
  await expect(page.getByRole("switch", { name: "Security: by email" })).toBeDisabled();
  await expect(page.getByText("Always on: you need to know")).toBeVisible();
  const jobsEmail = page.getByRole("switch", { name: "Background jobs: by email" });
  await expect(jobsEmail).not.toBeChecked();
  await jobsEmail.click();
  await expect(jobsEmail).toBeChecked();
  await expect(page.locator("[data-prefs-status]")).toHaveText("Saved: Background jobs.");
  expect(sent).toEqual([{ category: "jobs", email: true }]);
  await expect(page.locator('[data-settings-nav] a[aria-current="page"]')).toHaveText(
    "Notifications",
  );
  await expectAccessible(page);
});
