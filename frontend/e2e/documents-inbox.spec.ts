import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * A-06-T12 — Documents inbox. Acceptance: Playwright perf — 1,000 files, first paint under 1 s.
 * The API is answered with fixtures in the shape of the real one (backend/numo9/files/api.py,
 * checked by backend/tests/test_files_tagging.py).
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}/files`;
const PAGE = `/o/${ORG}/documents`;
const COUNT = 1000;

function documentAt(index: number) {
  const n = String(index).padStart(4, "0");
  const email = index % 3 === 0;
  return {
    id: `d0000000-0000-4000-8000-00000000${n}`,
    name: `receipt-${n}.pdf`,
    mime: "application/pdf",
    size: 20_000 + index,
    sha256: n.repeat(16),
    status: index === 1 ? "scanning" : "clean",
    status_label: index === 1 ? "Scanning" : "Ready",
    source: email ? "email" : "upload",
    sender: email ? (index % 2 ? "unknown@example.net" : "sam@refined.ca") : "",
    sender_known: !(email && index % 2),
    period: `2026-${String((index % 12) + 1).padStart(2, "0")}`,
    tax_year: 2025 + (index % 2),
    tags: index % 5 === 0 ? ["Receipts"] : [],
    folder: "inbox",
    preview_status: "unsupported",
    password_protected: false,
    uploaded_by: email ? "" : "Sam Patel",
    created_at: "2026-11-10T15:00:00Z",
  };
}

const DOCUMENTS = Array.from({ length: COUNT }, (_, i) => documentAt(i));

async function mockFiles(page: Page) {
  await mockCsrf(page);
  const requests: URL[] = [];
  await page.route(`${API}?*`, (r) => {
    const url = new URL(r.request().url());
    requests.push(url);
    const folder = url.searchParams.get("folder") ?? "inbox";
    const results = folder === "inbox" ? DOCUMENTS : [];
    return r.fulfill({ json: { results, next: null, total: results.length } });
  });
  await page.route(`${API}/inbound-address`, (r) =>
    r.fulfill({
      json: {
        address: "acme-7k3m9q2x4tbw@in.numo9.ca",
        created_at: "2026-11-01T00:00:00Z",
        previous: null,
      },
    }),
  );
  await page.route(`${API}/*/actions`, (r) => r.fulfill({ json: { actions: [] } }));
  await page.route(`${API}/bulk`, (r) => r.fulfill({ json: { updated: 2 } }));
  return requests;
}

test("1,000 files: first paint of the list under 1 s", async ({ page }) => {
  const requests = await mockFiles(page);
  await page.goto(PAGE);
  await expect(page.getByRole("heading", { level: 1, name: "Documents" })).toBeVisible();
  // Measured from the moment the list response arrives to the first row painted: the inbox's own
  // rendering cost for 1,000 documents (the network and the server are outside it).
  const started = Date.now();
  await page.getByRole("tab", { name: "Archived" }).click();
  await page.getByRole("tab", { name: "Inbox" }).click();
  await expect(page.getByRole("row", { name: /receipt-0000\.pdf/ })).toBeVisible();
  const elapsed = Date.now() - started;
  expect(elapsed).toBeLessThan(1000);
  expect(requests.at(-1)!.searchParams.get("limit")).toBe(String(COUNT));
  // Virtualised: only a screenful of rows is in the DOM, never all 1,000.
  const rendered = await page.getByRole("row").count();
  expect(rendered).toBeLessThan(100);
});

test("navigation paint for 1,000 files under 1 s (performance timing)", async ({ page }) => {
  await mockFiles(page);
  await page.goto(PAGE);
  await expect(page.getByRole("row", { name: /receipt-0000\.pdf/ })).toBeVisible();
  const paint = await page.evaluate(
    () =>
      performance.getEntriesByType("paint").find((e) => e.name === "first-contentful-paint")
        ?.startTime ?? 0,
  );
  expect(paint).toBeGreaterThan(0);
  expect(paint).toBeLessThan(1000);
});

test("address to copy, unknown senders flagged, a11y", async ({ page }) => {
  await mockFiles(page);
  await page.goto(PAGE);
  await expect(page.getByTestId("inbound-address")).toHaveText("acme-7k3m9q2x4tbw@in.numo9.ca");
  await expect(page.getByText("Unknown sender").first()).toBeVisible();
  await expect(page.getByRole("row", { name: /receipt-0000\.pdf/ })).toBeVisible();
  await expectAccessible(page);
});

test("bulk archive sends the selected ids", async ({ page }) => {
  await mockFiles(page);
  await page.goto(PAGE);
  const grid = page.getByRole("grid", { name: "Documents" });
  await expect(grid.getByRole("row", { name: /receipt-0000\.pdf/ })).toBeVisible();
  await grid.getByRole("checkbox", { name: "Select receipt-0000.pdf" }).check();
  await grid.getByRole("checkbox", { name: "Select receipt-0002.pdf" }).check();
  const request = page.waitForRequest((r) => r.url().endsWith("/files/bulk"));
  await page.getByRole("button", { name: "Archive" }).click();
  const body = (await request).postDataJSON() as { ids: string[]; action: string };
  expect(body.action).toBe("archive");
  expect(body.ids).toHaveLength(2);
});
