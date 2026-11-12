import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, expectNoHorizontalScroll, mockCsrf } from "./auth-helpers";

/**
 * A-08-T07 — job tray. Acceptance: a bulk job shows progress. The job tray API is answered in
 * the shape of the real one (backend/numo9/jobs/api.py, tested in backend/tests/test_job_api.py):
 * `GET jobs` for the first list, then the Server-Sent Events stream `jobs/events`, whose every
 * connection here sends the next stage of the job (the real stream sends each change and
 * EventSource reconnects the same way when it ends).
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}`;
const JOB_ID = "a1b2c3d4-0000-4000-8000-000000000001";

function job(overrides: Record<string, unknown> = {}) {
  return {
    id: JOB_ID,
    type: "numo9.contacts.bulk_archive",
    label: "Archive contacts",
    status: "running",
    status_label: "Running",
    progress: { done: 0, total: 250, percent: 0, message: "" },
    result_url: "",
    error: null,
    can_retry: false,
    attempts: 1,
    created_at: "2026-11-12T14:00:00Z",
    started_at: "2026-11-12T14:00:01Z",
    finished_at: null,
    next_retry_at: null,
    ...overrides,
  };
}

const running = (done: number) =>
  job({
    progress: {
      done,
      total: 250,
      percent: Math.floor((done * 100) / 250),
      message: `Contact ${done} of 250`,
    },
  });

const succeeded = job({
  status: "succeeded",
  status_label: "Done",
  progress: { done: 250, total: 250, percent: 100, message: "" },
  result_url: `/o/${ORG}/contacts?archived=1`,
  finished_at: "2026-11-12T14:02:00Z",
});

function sse(...events: [string, unknown][]): string {
  return (
    "retry: 150\n\n" +
    events.map(([name, data]) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`).join("")
  );
}

/**
 * Answers the job tray API. Stream connection n sends `stages[n]`; the first is sent at once, each
 * later one when the test calls `next()` — so the test sees every stage.
 */
async function mockJobs(page: Page, first: unknown[], stages: string[]) {
  await mockCsrf(page);
  const streams: string[] = [];
  const retries: string[] = [];
  const released: (() => void)[] = [];
  const gates = stages.map((_, i) =>
    i === 0 ? Promise.resolve() : new Promise<void>((resolve) => released.push(resolve)),
  );
  await page.route(`${API}/jobs`, (r) => r.fulfill({ json: first }));
  await page.route(`${API}/jobs/events`, async (r) => {
    const index = Math.min(streams.length, stages.length - 1);
    streams.push(r.request().headers()["accept"] ?? "");
    await gates[index];
    await r.fulfill({ status: 200, contentType: "text/event-stream", body: stages[index]! });
  });
  await page.route(`${API}/jobs/*/retry`, async (r) => {
    retries.push(r.request().url());
    await r.fulfill({
      status: 202,
      json: job({ status: "queued", status_label: "Waiting to start", attempts: 3 }),
    });
  });
  return { streams, retries, next: () => released.shift()?.() };
}

async function openTray(page: Page, name: string | RegExp = /Background jobs/) {
  await page.getByRole("banner").getByRole("button", { name }).click();
  const tray = page.getByRole("dialog", { name: "Background jobs" });
  await expect(tray).toBeVisible();
  return tray;
}

test.use({ viewport: { width: 1280, height: 900 } });

test("a bulk job shows its progress until it is done", async ({ page }) => {
  const { streams, next } = await mockJobs(
    page,
    [running(0)],
    [
      sse(["jobs", [running(50)]]),
      sse(["jobs", [running(150)]]),
      sse(["jobs", [succeeded]], ["idle", { active: 0 }]),
    ],
  );
  await page.goto(`/o/${ORG}/home`);
  const tray = await openTray(page, "Background jobs: 1 running");
  const bar = tray.getByRole("progressbar", { name: "Archive contacts" });
  await expect(bar).toHaveAttribute("aria-valuenow", "20");
  await expect(tray.getByText("Contact 50 of 250")).toBeVisible();
  next();
  await expect(bar).toHaveAttribute("aria-valuenow", "60");
  await expect(tray.getByText("Contact 150 of 250")).toBeVisible();
  next();
  await expect(tray.getByRole("link", { name: "Open the result" })).toHaveAttribute(
    "href",
    `/o/${ORG}/contacts?archived=1`,
  );
  await expect(tray.getByText("Done", { exact: true })).toBeVisible();
  await expect(bar).toHaveCount(0);
  expect(streams[0]).toContain("text/event-stream");
  const after = streams.length;
  await page.waitForTimeout(600); // idle: the tray stops following the stream
  expect(streams.length).toBe(after);
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("banner").getByRole("button", { name: "Background jobs", exact: true }),
  ).toBeVisible(); // nothing running any more
});

test("a failed job shows its error and can be started again", async ({ page }) => {
  const failed = job({
    status: "dead",
    status_label: "Failed after several tries",
    progress: { done: 3, total: 250, percent: 1, message: "Contact 3 of 250" },
    error: {
      code: "job.failed",
      message:
        "Something went wrong while this job was running. Try again; if it fails again, contact Numo9 support with the job's reference.",
    },
    can_retry: true,
    attempts: 6,
    finished_at: "2026-11-12T14:20:00Z",
  });
  const { retries, next } = await mockJobs(
    page,
    [failed],
    [
      sse(["jobs", [job({ status: "queued", status_label: "Waiting to start", attempts: 6 })]]),
      sse(["jobs", [running(250)]]),
      sse(["jobs", [succeeded]], ["idle", { active: 0 }]),
    ],
  );
  await page.goto(`/o/${ORG}/home`);
  const tray = await openTray(page, "Background jobs");
  await expect(tray.getByText("Failed after several tries")).toBeVisible();
  await expect(tray.getByText(/Something went wrong while this job was running/)).toBeVisible();
  await expect(tray.getByText("Reference: a1b2c3d4")).toBeVisible();
  await tray.getByRole("button", { name: "Try again" }).click();
  await expect(tray.getByText("Waiting to start")).toBeVisible();
  await expect(tray.getByText("Waiting for a free server…")).toBeVisible();
  next();
  await expect(tray.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  next();
  await expect(tray.getByRole("link", { name: "Open the result" })).toBeVisible();
  expect(retries).toEqual([expect.stringContaining(`/jobs/${JOB_ID}/retry`)]);
});

test("the tray is hidden until there is a job, and accessible when open", async ({ page }) => {
  await mockJobs(page, [], []);
  await page.goto(`/o/${ORG}/home`);
  await expect(
    page.getByRole("banner").getByRole("button", { name: "Account menu" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /Background jobs/ })).toHaveCount(0);

  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mockJobs(page, [running(125)], [sse(["jobs", [running(125)]])]);
  await page.reload();
  await openTray(page);
  await expectAccessible(page);
  await expectNoHorizontalScroll(page);
});
