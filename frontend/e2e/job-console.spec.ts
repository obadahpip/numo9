import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, expectNoHorizontalScroll, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * A-08-T08 — internal job dashboard in the platform console (`/console/jobs`). Acceptance: the
 * platform owner sees failures (the plan's manual check, scripted here on fixtures in the API's
 * shape — backend/numo9/jobs/console.py, tested against the real service in
 * backend/tests/test_job_console.py).
 */
const API = "**/api/v1/platform/jobs";
const DEAD_ID = "d3ad0000-1111-4222-8333-444455556666";

const overview = {
  queues: [
    { name: "high", waiting_messages: 0, queued: 0, running: 0, retrying: 0 },
    { name: "default", waiting_messages: 4, queued: 4, running: 1, retrying: 0 },
    { name: "io", waiting_messages: null, queued: 0, running: 0, retrying: 2 },
    { name: "reports", waiting_messages: 1, queued: 1, running: 2, retrying: 0 },
  ],
  counts: { queued: 5, running: 3, retrying: 2, succeeded_24h: 118, failed_24h: 1, dead: 2 },
};

function consoleJob(overrides: Record<string, unknown> = {}) {
  return {
    id: DEAD_ID,
    type: "numo9.banking.import_feed",
    label: "Bank feed import",
    status: "dead",
    status_label: "Failed after several tries",
    progress: { done: 0, total: null, percent: null, message: "" },
    result_url: "",
    error: { code: "job.failed", message: "Something went wrong while this job was running." },
    can_retry: true,
    attempts: 6,
    created_at: "2026-11-12T09:00:00Z",
    started_at: "2026-11-12T09:00:02Z",
    finished_at: "2026-11-12T09:41:00Z",
    next_retry_at: null,
    organisation: { id: "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6", name: "Maple Leaf Supply Ltd." },
    created_by: { id: "u-1", name: "Dana Lee", email: "dana@maple.ca" },
    queue: "io",
    payload: { org_id: "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6", account: "[REDACTED]" },
    error_detail: "builtins.ConnectionError: bank feed provider timed out",
    worker: "worker-io-1:4242",
    celery_task_id: "6c1b0f9e-2d7a-4e8b-9c3d-1a2b3c4d5e6f",
    idempotency_key: "numo9.banking.import_feed:7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6:feed-9",
    max_retries: 5,
    ...overrides,
  };
}

async function mockConsole(page: Page, { manage = true }: { manage?: boolean } = {}) {
  await mockCsrf(page);
  const lists: string[] = [];
  const posts: { url: string; body: unknown }[] = [];
  let rows = [consoleJob()];
  await page.route(`${API}/overview`, (r) => r.fulfill({ json: overview }));
  await page.route(`${API}?*`, (r) => {
    lists.push(r.request().url());
    return r.fulfill({ json: { count: rows.length, results: rows } });
  });
  const refuse = {
    status: 403,
    json: {
      code: "permission.denied",
      detail: "You don't have permission to retry or purge background jobs.",
    },
  };
  await page.route(`${API}/*/retry`, async (r) => {
    posts.push({ url: r.request().url(), body: jsonBody(r) });
    if (!manage) return r.fulfill(refuse);
    rows = [
      consoleJob({
        status: "queued",
        status_label: "Waiting to start",
        error: null,
        can_retry: false,
      }),
    ];
    return r.fulfill({ status: 202, json: rows[0] });
  });
  await page.route(`${API}/purge`, async (r) => {
    const body = jsonBody(r);
    posts.push({ url: r.request().url(), body });
    if (!manage) return r.fulfill(refuse);
    rows = [];
    return r.fulfill({ json: { deleted: 1 } });
  });
  return { lists, posts };
}

test.use({ viewport: { width: 1280, height: 900 } });

test("the platform owner sees failures and retries one", async ({ page }) => {
  const { lists, posts } = await mockConsole(page);
  await page.goto("/console/jobs");
  await expect(page.getByRole("heading", { level: 1, name: "Background jobs" })).toBeVisible();
  // Counts and queues.
  const dead = page.getByRole("definition").filter({ hasText: /^2$/ });
  await expect(dead.first()).toBeVisible();
  await expect(page.getByText("Failed (24 h)")).toBeVisible();
  const io = page.locator('[data-queue="io"]');
  await expect(io.getByRole("cell").first()).toHaveText("Unknown"); // broker not reachable
  await expect(page.locator('[data-queue="default"]').getByRole("cell").first()).toHaveText("4");
  // The failure, with its organisation, error and technical detail.
  const row = page.locator(`[data-console-job="${DEAD_ID}"]`);
  await expect(row.getByText("Bank feed import")).toBeVisible();
  await expect(row.getByText("Maple Leaf Supply Ltd.")).toBeVisible();
  await expect(row.getByText("Failed after several tries")).toBeVisible();
  await expect(row.getByText("6 of 6")).toBeVisible();
  await expect(row.getByText("Something went wrong while this job was running.")).toBeVisible();
  await row.getByRole("button", { name: "Details" }).click();
  const details = row.getByLabel("Technical details of d3ad0000");
  await expect(
    details.getByText("builtins.ConnectionError: bank feed provider timed out"),
  ).toBeVisible();
  await expect(details.getByText(/\[REDACTED\]/)).toBeVisible();
  expect(lists[0]).toContain("status=dead"); // dead letters first
  await expectAccessible(page);

  await row.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("status")).toHaveText("d3ad0000 is queued again.");
  await expect(row.getByText("Waiting to start")).toBeVisible();
  expect(posts).toEqual([{ url: expect.stringContaining(`/${DEAD_ID}/retry`), body: {} }]);
});

test("dead letters are purged — chosen ones or the old ones", async ({ page }) => {
  const { posts } = await mockConsole(page);
  await page.goto("/console/jobs");
  const purge = page.getByRole("button", { name: /Purge 0 selected jobs/ });
  await expect(purge).toBeDisabled();
  await page.getByRole("checkbox", { name: "Select d3ad0000" }).click();
  await page.getByRole("button", { name: "Purge 1 selected job" }).click();
  await expect(page.getByRole("status")).toHaveText("1 job purged.");
  await expect(page.getByText("No jobs match these filters.")).toBeVisible();
  await page.getByRole("button", { name: "Purge dead jobs older than 7 days" }).click();
  expect(posts.map((p) => p.body)).toEqual([
    { ids: [DEAD_ID] },
    { status: "dead", older_than_days: 7 },
  ]);
});

test("filters and search reach the API", async ({ page }) => {
  const { lists } = await mockConsole(page);
  await page.goto("/console/jobs");
  await expect(page.locator(`[data-console-job="${DEAD_ID}"]`)).toBeVisible();
  await page.getByRole("combobox", { name: "Status" }).click();
  await page.getByRole("option", { name: "Any" }).click();
  await page.getByRole("combobox", { name: "Queue" }).click();
  await page.getByRole("option", { name: "io" }).click();
  await page.getByRole("searchbox", { name: "Search" }).fill("maple");
  await page.getByRole("button", { name: "Show" }).click();
  await expect.poll(() => lists.length).toBe(2);
  const url = new URL(lists[1]!);
  expect(url.searchParams.get("status")).toBeNull();
  expect(url.searchParams.get("queue")).toBe("io");
  expect(url.searchParams.get("q")).toBe("maple");
});

test("platform support can look but is told why it can't retry", async ({ page }) => {
  await mockConsole(page, { manage: false });
  await page.goto("/console/jobs");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("status")).toHaveText(
    "You don't have permission to retry or purge background jobs.",
  );
});

test("someone without console access sees why", async ({ page }) => {
  await mockCsrf(page);
  await page.route(`${API}/overview`, (r) =>
    r.fulfill({
      status: 403,
      json: {
        code: "permission.denied",
        detail: "You don't have permission to see background jobs and failures.",
      },
    }),
  );
  await page.route(`${API}?*`, (r) =>
    r.fulfill({ status: 403, json: { code: "permission.denied" } }),
  );
  await page.goto("/console/jobs");
  await expect(
    page.getByRole("heading", { level: 1, name: "You can't open the job dashboard" }),
  ).toBeVisible();
  await expect(
    page.getByText("You don't have permission to see background jobs and failures."),
  ).toBeVisible();
});

test.describe("at 360 px", () => {
  test.use({ viewport: { width: 360, height: 800 } });

  test("the dashboard fits without horizontal scroll", async ({ page }) => {
    await mockConsole(page);
    await page.goto("/console/jobs");
    await expect(page.locator(`[data-console-job="${DEAD_ID}"]`)).toBeVisible();
    await expectNoHorizontalScroll(page);
    await expectAccessible(page);
  });
});
