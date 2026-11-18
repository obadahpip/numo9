import { expect, test, type BrowserContext, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * V-01-T09…T15 — organisation directory `/p/:practice/directory` (production build).
 *
 * The API is answered by a fixture server in the shape of the real one
 * (backend/numo9/workspace/api.py, docs/architecture/directory.md): 2,000 organisations, the same
 * search rules (accent-insensitive word prefixes, BN digits across spaces), filters (OR within,
 * AND across) and facets (every other filter applied). The server-side rules themselves are proven
 * by backend/tests/test_workspace_*.py; here the screen's wiring is checked in a real browser.
 */
const PRACTICE = "6ca1b880-64f7-4053-80e3-0c3618895553";
const PAGE = `/p/${PRACTICE}/directory`;
const COUNT = 2000;

const FIRST = ["Maple", "Érable", "Birch", "Cedar", "Prairie", "Harbour", "Granite", "Fundy"];
const TRADE = ["Supply", "Bakery", "Dental", "Movers", "Tile Co.", "Consulting", "Café", "Farms"];
const PROVINCES = ["ON", "ON", "ON", "QC", "QC", "BC", "AB", "NS"];
const PROVINCE_NAMES: Record<string, string> = {
  ON: "Ontario",
  QC: "Quebec",
  BC: "British Columbia",
  AB: "Alberta",
  NS: "Nova Scotia",
};
const STATUSES = ["paid", "paid", "paid", "trial", "paid", "demo", "read_only", "archived"];
const PACKAGES = [
  ["books", "Books"],
  ["growth", "Growth"],
  ["complete", "Complete"],
];

interface Org {
  id: string;
  name: string;
  bn: string;
  province: string;
  package: string;
  package_name: string;
  status: string;
  trial_days_left: number | null;
  fye_month: number;
  fye_day: number;
  overdue_count: number;
}

function orgAt(index: number): Org {
  const [code, name] = PACKAGES[index % 3]!;
  const status = STATUSES[index % 8]!;
  return {
    id: `00000000-0000-4000-8000-${String(index).padStart(12, "0")}`,
    name: `${FIRST[index % 8]} ${TRADE[Math.floor(index / 8) % 8]} ${index + 1}`,
    bn: index === 9 ? "123456789" : String(200000000 + index * 37),
    province: PROVINCES[(index * 3) % 8]!,
    package: code!,
    package_name: name!,
    status,
    trial_days_left: status === "trial" ? (index % 30) + 1 : null,
    fye_month: [12, 12, 3, 6][index % 4]!,
    fye_day: [31, 31, 31, 30][index % 4]!,
    overdue_count: index % 5 === 0 ? index % 4 : 0,
  };
}

const ORGS = Array.from({ length: COUNT }, (_, i) => orgAt(i));

const fold = (text: string) =>
  text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase();

type Filters = Record<string, string[]>;
const FACET_KEYS = ["package", "status", "province", "fye", "overdue"] as const;

function value(org: Org, key: string): string {
  if (key === "fye") return String(org.fye_month);
  if (key === "overdue") return org.overdue_count > 0 ? "yes" : "no";
  return String(org[key as keyof Org]);
}

function search(params: URLSearchParams): { visible: Org[]; filters: Filters } {
  const q = params.get("q") ?? "";
  const archived = params.get("archived") === "include";
  const filters: Filters = {};
  for (const key of FACET_KEYS) {
    const values = params.getAll(key);
    if (values.length) filters[key] = values;
  }
  const words = fold(q).match(/[a-z0-9]+/g) ?? [];
  const digits = q.replace(/[\s-]/g, "");
  const visible = ORGS.filter((org) => {
    if (org.status === "archived" && !archived && !filters.status?.includes("archived"))
      return false;
    if (!q.trim()) return true;
    const text = fold(`${org.name} ${org.bn} ${org.province} ${PROVINCE_NAMES[org.province]}`);
    const tokens = text.split(/[^a-z0-9]+/);
    const byWords = words.every((w) => tokens.some((t) => t.startsWith(w)));
    const byBn = /^\d{3,}$/.test(digits) && org.bn.includes(digits);
    return byWords || byBn;
  });
  return { visible, filters };
}

function passes(org: Org, filters: Filters, skip?: string): boolean {
  return Object.entries(filters).every(
    ([key, values]) => key === skip || values.includes(value(org, key)),
  );
}

function answer(url: URL) {
  const { visible, filters } = search(url.searchParams);
  const matching = visible.filter((org) => passes(org, filters));
  const facets: Record<string, { value: string; label: string; count: number }[]> = {};
  for (const key of FACET_KEYS) {
    const counts = new Map<string, number>();
    for (const org of visible.filter((o) => passes(o, filters, key))) {
      counts.set(value(org, key), (counts.get(value(org, key)) ?? 0) + 1);
    }
    facets[key] = [...counts].map(([v, count]) => ({
      value: v,
      label: key === "province" ? PROVINCE_NAMES[v]! : v,
      count,
    }));
  }
  const size = Number(url.searchParams.get("page_size") ?? 50);
  return {
    practice: { id: PRACTICE, name: "Abuodeh CPA" },
    count: matching.length,
    total: search(new URLSearchParams(url.searchParams.get("archived") ? "archived=include" : ""))
      .visible.length,
    page: 1,
    page_size: size,
    pages: Math.max(1, Math.ceil(matching.length / size)),
    columns: (url.searchParams.get("columns") ?? "").split(","),
    results: matching.slice(0, size),
    facets: { ...facets, gst_cycle: [], payroll: [], unfiled: [], tag: [] },
  };
}

interface ViewsStore {
  views: Record<string, unknown>[];
}

/** The API, with a saved-views store shared across browser contexts (the "server"). */
async function mockApi(target: Page | BrowserContext, store: ViewsStore = { views: [] }) {
  const requests: URL[] = [];
  await target.route("**/api/v1/auth/csrf", (r) => r.fulfill({ json: { csrfToken: "t" } }));
  await target.route("**/api/v1/practice/orgs?*", (route) => {
    const url = new URL(route.request().url());
    requests.push(url);
    return route.fulfill({ json: answer(url) });
  });
  await target.route("**/api/v1/practice/views**", async (route) => {
    const request = route.request();
    if (request.method() === "POST") {
      const body = request.postDataJSON() as Record<string, unknown>;
      const saved = {
        id: `v-${store.views.length + 1}`,
        practice: PRACTICE,
        is_default: false,
        created_at: "",
        updated_at: "",
        columns: [],
        sort: [],
        density: "comfortable",
        ...body,
      };
      store.views.push(saved);
      return route.fulfill({ status: 201, json: saved });
    }
    if (request.method() === "PATCH") {
      const id = new URL(request.url()).pathname.split("/").pop();
      const found = store.views.find((v) => v.id === id)!;
      Object.assign(found, request.postDataJSON());
      return route.fulfill({ json: found });
    }
    return route.fulfill({ json: store.views });
  });
  return requests;
}

const rows = (page: Page) => page.locator("[data-directory] [data-row-index]");
const summary = (page: Page) => page.locator("[data-directory-summary]");

test("T09 — 2,000 organisations render virtualised and scroll smoothly", async ({ page }) => {
  await mockApi(page);
  await page.goto(PAGE);
  await expect(page.getByRole("heading", { level: 1, name: "Organisations" })).toBeVisible();
  await expect(summary(page)).toContainText("1,750 organisations assigned to Abuodeh CPA");
  await expect(page.getByRole("grid", { name: "Organisations" })).toHaveAttribute(
    "aria-rowcount",
    "1751",
  );
  expect(await rows(page).count()).toBeLessThan(100); // only a screenful is in the DOM
  // Sticky header and status chips
  await expect(page.getByRole("columnheader", { name: /Organisation/ })).toHaveCSS(
    "position",
    "sticky",
  );
  await expect(rows(page).first().locator("[data-status]")).toBeVisible();
  // Scroll the whole list, one step per frame: frames stay near 60 fps.
  const frames = await page.evaluate(async () => {
    const scroller = document.querySelector<HTMLElement>("[data-directory] [data-grid-scroller]")!;
    const deltas: number[] = [];
    let last = performance.now();
    const step = scroller.scrollHeight / 240;
    for (let i = 0; i < 240; i += 1) {
      scroller.scrollTop += step;
      await new Promise(requestAnimationFrame);
      const now = performance.now();
      deltas.push(now - last);
      last = now;
    }
    return deltas.sort((a, b) => a - b);
  });
  const median = frames[Math.floor(frames.length / 2)]!;
  expect(median, `median frame ${median.toFixed(1)} ms`).toBeLessThan(20); // ≈ 60 fps
  await expect(rows(page).last()).toContainText(/\d/);
});

test("T10 — typing BN “123 456” finds 123456789 (debounced, highlighted)", async ({ page }) => {
  const requests = await mockApi(page);
  await page.goto(PAGE);
  await expect(rows(page).first()).toBeVisible();
  const before = requests.length;
  await page.getByRole("searchbox", { name: "Search organisations" }).pressSequentially("123 456", {
    delay: 30,
  });
  await expect(rows(page)).toHaveCount(1);
  await expect(rows(page).first()).toContainText("123 456 789");
  await expect(rows(page).first().locator("mark")).toHaveText("123 456");
  // one request after typing stopped (150 ms debounce), not one per key
  expect(requests.length - before).toBeLessThanOrEqual(2);
  expect(requests.at(-1)!.searchParams.get("q")).toBe("123 456");
});

test("T11 — facet count = result count after applying", async ({ page }) => {
  await mockApi(page);
  await page.goto(PAGE);
  await expect(rows(page).first()).toBeVisible();
  await page.getByRole("button", { name: "Filters" }).click();
  const panel = page.getByRole("complementary", { name: "Filters" });
  for (const group of ["province", "package", "fye", "overdue"]) {
    const options = panel.locator(`[data-facet="${group}"] [data-option]`);
    await expect(options.first()).toBeVisible();
    let picked = -1;
    for (let i = 0; i < (await options.count()); i += 1) {
      if (Number(await options.nth(i).getAttribute("data-count")) > 0) {
        picked = i;
        break;
      }
    }
    expect(picked, `an option with organisations in ${group}`).toBeGreaterThanOrEqual(0);
    const item = options.nth(picked);
    const count = Number(await item.getAttribute("data-count"));
    await item.getByRole("checkbox").click();
    await expect(summary(page)).toContainText(`${count.toLocaleString("en-CA")} of 1,750`);
  }
});

test("T12 — a saved view persists after logout/login and follows the user", async ({
  browser,
  baseURL,
}) => {
  const store: ViewsStore = { views: [] };
  const first = await browser.newContext({ baseURL });
  await mockApi(first, store);
  const page = await first.newPage();
  await page.goto(PAGE);
  await expect(rows(page).first()).toBeVisible();
  await page.getByRole("button", { name: "Filters" }).click();
  await page
    .getByRole("complementary", { name: "Filters" })
    .locator('[data-facet="province"] [data-option="AB"]')
    .getByRole("checkbox")
    .click();
  await page.getByRole("button", { name: "Columns" }).click();
  await page.getByRole("checkbox", { name: "Owner" }).click(); // show the Owner column
  await page.keyboard.press("Escape");
  await page
    .getByRole("navigation", { name: "Saved views" })
    .getByRole("button", {
      name: "Save current view",
    })
    .click();
  await page.getByRole("textbox", { name: "View name" }).fill("BC clients");
  await page.getByRole("dialog").getByRole("button", { name: "Save view" }).click();
  await expect(page.getByText("View “BC clients”", { exact: true })).toBeVisible();
  // set it as default from its menu
  await page.getByRole("button", { name: "Options for view BC clients" }).click();
  await page.getByRole("button", { name: "Set as default" }).click();
  await first.close(); // logout: the browser's state is gone

  const second = await browser.newContext({ baseURL }); // login again, another browser
  const requests = await mockApi(second, store);
  const again = await second.newPage();
  await again.goto(PAGE);
  const rail = again.getByRole("navigation", { name: "Saved views" });
  await expect(rail.getByRole("button", { name: /^BC clients/ })).toHaveAttribute(
    "aria-current",
    "true",
  );
  await expect(
    again.getByRole("button", { name: "Remove filter Province: Alberta" }),
  ).toBeVisible();
  await expect(again.getByRole("columnheader", { name: /Owner/ })).toBeVisible();
  expect(requests[0]!.searchParams.getAll("province")).toEqual(["AB"]);
  await second.close();
});

test("T13 — every action without a mouse; Ctrl/⌘+K goes to an organisation", async ({ page }) => {
  await mockApi(page);
  await page.goto(PAGE);
  await expect(rows(page).first()).toBeVisible();
  // "/" search, ↓ into the rows, Enter opens
  await page.keyboard.press("/");
  await expect(page.getByRole("searchbox", { name: "Search organisations" })).toBeFocused();
  await page.keyboard.type("maple");
  await expect(rows(page).first()).toContainText("Maple");
  await page.keyboard.press("ArrowDown");
  await expect(rows(page).first()).toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(rows(page).nth(1)).toBeFocused();
  // F opens the filters panel; Tab reaches its options; Space ticks one
  await page.keyboard.press("Escape");
  await page.locator("body").focus();
  await page.keyboard.press("f");
  const panel = page.getByRole("complementary", { name: "Filters" });
  await expect(panel).toBeVisible();
  await panel.getByRole("checkbox").first().focus();
  await page.keyboard.press("Space");
  await expect(page.getByRole("button", { name: /Filters \(1\)/ })).toBeVisible();
  await expectAccessible(page);
  // Ctrl+K → type → Enter lands on the organisation's Home
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: "Go to organisation" });
  await expect(dialog).toBeVisible();
  await page.keyboard.type("123 456");
  await expect(dialog.getByRole("option")).toHaveCount(1);
  await expectAccessible(page);
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`/o/${orgAt(9).id}/home$`));
});

test("T15 — accessible at desktop and phone width, sort state announced", async ({ page }) => {
  await mockApi(page);
  for (const width of [1280, 360]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto(PAGE);
    await expect(rows(page).first()).toBeVisible();
    await expectAccessible(page);
  }
  await page.setViewportSize({ width: 1280, height: 800 });
  const header = page.getByRole("columnheader", { name: /Overdue/ });
  await expect(header).toHaveAttribute("aria-sort", "none");
  await header.getByRole("button").click();
  await expect(header).toHaveAttribute("aria-sort", "ascending");
  await page.getByRole("button", { name: "Filters" }).click();
  await expectAccessible(page);
});

test("T15 — French", async ({ browser, baseURL }) => {
  const context = await browser.newContext({ baseURL });
  await context.addCookies([{ name: "numo9_locale", value: "fr-CA", url: baseURL! }]);
  await mockApi(context);
  const page = await context.newPage();
  await page.goto(PAGE);
  await expect(page.locator("html")).toHaveAttribute("lang", "fr-CA");
  await expect(rows(page).first()).toBeVisible();
  await expectAccessible(page);
  await context.close();
});

// ---- T14: states, visual regression -----------------------------------------------------------

const FIXED_NOW = new Date("2026-10-26T14:00:00-04:00");

test.describe("@visual directory states", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  async function shoot(page: Page, name: string) {
    await page.clock.setFixedTime(FIXED_NOW);
    await page.goto(PAGE);
    await expect(page.locator("[data-grid-state], [data-row-index]").first()).toBeVisible();
    await expect(page).toHaveScreenshot(`directory-${name}.png`, { fullPage: false });
  }

  test("ready", async ({ page }) => {
    await mockApi(page);
    await shoot(page, "ready");
  });

  test("empty (first run)", async ({ page }) => {
    await mockCsrf(page);
    await page.route("**/api/v1/practice/views**", (r) => r.fulfill({ json: [] }));
    await page.route("**/api/v1/practice/orgs?*", (r) =>
      r.fulfill({ json: { ...answer(new URL("http://x/?q=zzzz")), total: 0, facets: {} } }),
    );
    await shoot(page, "empty");
    await expect(
      page.getByRole("heading", { name: "Your practice has no organisations yet" }),
    ).toBeVisible();
  });

  test("no results", async ({ page }) => {
    await mockApi(page);
    await page.clock.setFixedTime(FIXED_NOW);
    await page.goto(PAGE);
    await expect(rows(page).first()).toBeVisible();
    await page.getByRole("searchbox", { name: "Search organisations" }).fill("zzzz");
    await expect(page.getByRole("heading", { name: "No organisations match" })).toBeVisible();
    await expect(page).toHaveScreenshot("directory-no-results.png");
  });

  test("loading (skeleton)", async ({ page }) => {
    await mockCsrf(page);
    await page.route("**/api/v1/practice/views**", (r) => r.fulfill({ json: [] }));
    await page.route("**/api/v1/practice/orgs?*", () => new Promise(() => undefined));
    await page.clock.setFixedTime(FIXED_NOW);
    await page.goto(PAGE);
    await expect(page.getByRole("grid")).toHaveAttribute("aria-busy", "true");
    await expect(page).toHaveScreenshot("directory-loading.png");
  });

  test("error (retry)", async ({ page }) => {
    await mockCsrf(page);
    await page.route("**/api/v1/practice/views**", (r) => r.fulfill({ json: [] }));
    await page.route("**/api/v1/practice/orgs?*", (r) => r.fulfill({ status: 500, json: {} }));
    await shoot(page, "error");
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  });
});

// ---- bulk actions (V-03-T08, T09) -----------------------------------------------------------

test("select all matching sends the search as a query, previews, then applies", async ({
  page,
}) => {
  await mockApi(page);
  await mockCsrf(page);
  const bodies: Record<string, unknown>[] = [];
  const job = {
    id: "job-1",
    action: "export",
    action_label: "Export the list",
    params: { format: "csv" },
    status: "preview",
    total: 0,
    done: 0,
    percent: 0,
    counts: { pending: 0, succeeded: 0, skipped: 0, failed: 0, cancelled: 0 },
    created_by: { id: "u", name: "Sam" },
    created_at: "2026-11-18T15:00:00Z",
    started_at: null,
    finished_at: null,
    cancel_requested: false,
    export_ready: false,
  };
  await page.route("**/api/v1/practice/bulk", (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    bodies.push(body);
    return route.fulfill({
      status: 201,
      json: {
        job: { ...job, total: 250 },
        preview: {
          total: 250,
          counts: { change: 250, no_change: 0, skipped: 0 },
          lines: [
            {
              organisation: { id: "o", name: "Maple Supply" },
              status: "change",
              reason: "",
              message: "",
              before: {},
              after: { name: "Maple Supply" },
            },
          ],
        },
      },
    });
  });
  let confirmed = false;
  await page.route("**/api/v1/practice/bulk/job-1/confirm", (route) => {
    confirmed = true;
    return route.fulfill({ status: 202, json: { ...job, status: "queued", total: 250 } });
  });
  let polls = 0;
  await page.route("**/api/v1/practice/bulk/job-1", (route) => {
    polls += 1;
    const done = Math.min(250, polls * 100);
    return route.fulfill({
      json: {
        ...job,
        status: done === 250 ? "completed" : "running",
        total: 250,
        done,
        percent: Math.floor((done * 100) / 250),
        counts: { pending: 250 - done, succeeded: done, skipped: 0, failed: 0, cancelled: 0 },
      },
    });
  });
  await page.route("**/api/v1/practice/bulk/job-1/rows*", (route) =>
    route.fulfill({ json: { count: 0, page: 1, pages: 1, results: [] } }),
  );

  await page.goto(PAGE);
  // Wait for the debounced search request: "all matching" made before it lands would be
  // cleared by the new query.
  const searched = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/practice/orgs?") &&
      new URL(response.url()).searchParams.get("q") === "Maple",
  );
  await page.locator("[data-directory] [data-grid-search]").fill("Maple");
  await searched;
  await expect(rows(page).first()).toContainText("Maple");
  await rows(page).first().getByRole("checkbox").check();
  const bar = page.locator("[data-bulk-bar]");
  await expect(bar).toContainText("1 selected");
  await bar.getByRole("button", { name: /^Select all .* matching$/ }).click();
  await expect(bar).toContainText(/organisations matching are selected/);
  await bar.getByRole("button", { name: "Export" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: "Preview changes" }).click();
  await expect(dialog.getByText("250 will change")).toBeVisible();
  expect(bodies[0]?.selection).toEqual({ query: { q: "Maple" } });
  expect(JSON.stringify(bodies[0])).not.toContain('"ids"');
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Apply to 250 organisations" }).click();
  await expect.poll(() => confirmed).toBe(true);
  // V-03-T10: the progress drawer's counters follow the job live
  const drawer = page.getByRole("dialog", { name: "Export the list" });
  await expect(drawer.locator('[data-counter="succeeded"] dd')).toHaveText("100");
  await expect(drawer.locator('[data-counter="succeeded"] dd')).toHaveText("200");
  await expect(drawer.locator('[data-counter="succeeded"] dd')).toHaveText("250");
  await expect(drawer.getByRole("link", { name: "Download the results (CSV)" })).toBeVisible();
});
