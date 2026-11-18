import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import {
  directoryQuery,
  formatBn,
  sameState,
  stateToView,
  viewToState,
  type DirectoryPage,
  type DirectoryRow,
  type SavedView,
} from "./api";
import { DEFAULT_STATE, DirectoryScreen } from "./DirectoryScreen";

/**
 * V-01-T09…T15 — organisation directory screen (component level, API answered by fixtures in the
 * shape of backend/numo9/workspace/api.py). Browser checks (2,000-row scroll, BN typing, facet =
 * result count, views after logout/login, keyboard-only flow, visual states, axe on the route) are
 * in e2e/directory.spec.ts.
 */

const PRACTICE = "6ca1b880-64f7-4053-80e3-0c3618895553";

function row(index: number, overrides: Partial<DirectoryRow> = {}): DirectoryRow {
  return {
    id: `0000000${index}-0000-4000-8000-000000000000`.slice(0, 36),
    name: `Org ${index}`,
    bn: "123456782",
    province: "ON",
    package: "growth",
    package_name: "Growth",
    status: "paid",
    trial_ends_at: null,
    trial_days_left: null,
    fye_month: 12,
    fye_day: 31,
    overdue_count: 0,
    ...overrides,
  };
}

const ROWS = [
  row(1, { name: "Maple Leaf Supply Ltd.", overdue_count: 3 }),
  row(2, {
    name: "Érable Bakery Inc.",
    bn: "874512993",
    province: "QC",
    status: "trial",
    trial_days_left: 12,
    fye_month: 3,
  }),
];

function page(results: DirectoryRow[], overrides: Partial<DirectoryPage> = {}): DirectoryPage {
  return {
    practice: { id: PRACTICE, name: "Abuodeh CPA" },
    count: results.length,
    total: 2,
    page: 1,
    page_size: 2000,
    pages: 1,
    columns: [],
    results,
    facets: {
      package: [{ value: "growth", label: "Growth", count: 2 }],
      status: [
        { value: "trial", label: "Trial", count: 1 },
        { value: "paid", label: "Paid", count: 1 },
        { value: "demo", label: "Demo", count: 0 },
      ],
      province: [
        { value: "ON", label: "Ontario", count: 1 },
        { value: "QC", label: "Quebec", count: 1 },
      ],
      fye: [{ value: "12", label: "December", count: 1 }],
      gst_cycle: [],
      payroll: [
        { value: "yes", label: "Yes", count: 2 },
        { value: "no", label: "No", count: 0 },
      ],
      overdue: [
        { value: "yes", label: "Yes", count: 1 },
        { value: "no", label: "No", count: 1 },
      ],
      unfiled: [
        { value: "yes", label: "Yes", count: 0 },
        { value: "no", label: "No", count: 2 },
      ],
      tag: [],
      group: [],
    },
    ...overrides,
  };
}

function view(overrides: Partial<SavedView> = {}): SavedView {
  return {
    id: "v1",
    practice: PRACTICE,
    name: "Ontario paid",
    filters: { province: ["ON"], status: ["paid"] },
    columns: ["name", "bn", "status"],
    sort: ["-overdue"],
    density: "compact",
    is_default: false,
    created_at: "2026-11-15T00:00:00Z",
    updated_at: "2026-11-15T00:00:00Z",
    ...overrides,
  };
}

const json = (body: unknown, status = 200) =>
  new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

interface Mock {
  list?: (url: URL) => Response | Promise<Response>;
  views?: SavedView[];
  viewsStatus?: number;
}

function mockApi({ list, views = [], viewsStatus = 200 }: Mock = {}) {
  const calls: { url: URL; init?: RequestInit }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = new URL(String(input), "http://numo9.test");
    calls.push({ url, init });
    if (url.pathname.endsWith("/csrf")) return json({ csrfToken: "token" });
    if (url.pathname === "/api/v1/practice/views") {
      if (init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as Partial<SavedView>;
        if (body.name === "Taken")
          return json({ detail: "You already have a view called Taken.", code: "x" }, 400);
        return json(view({ ...body, id: "v-new", is_default: false } as Partial<SavedView>), 201);
      }
      return json(views, viewsStatus);
    }
    if (url.pathname.startsWith("/api/v1/practice/views/")) {
      if (init?.method === "DELETE") return json(null, 204);
      const body = JSON.parse(String(init?.body ?? "{}")) as Partial<SavedView>;
      const current = views.find((v) => url.pathname.endsWith(v.id)) ?? view();
      return json({ ...current, ...body });
    }
    if (url.pathname === "/api/v1/practice/orgs") return list ? list(url) : json(page(ROWS));
    return json({}, 404);
  });
  const lists = () => calls.filter((c) => c.url.pathname === "/api/v1/practice/orgs");
  return { calls, lists };
}

function setup(props: Partial<Parameters<typeof DirectoryScreen>[0]> = {}) {
  const navigate = vi.fn();
  const openTab = vi.fn();
  const user = userEvent.setup();
  renderWithIntl(
    <DirectoryScreen practice={PRACTICE} navigate={navigate} openTab={openTab} {...props} />,
  );
  return { navigate, openTab, user };
}

const bodyRows = () =>
  within(screen.getByRole("grid", { name: "Organisations" }))
    .getAllByRole("row")
    .filter((r) => r.hasAttribute("data-row-index"));

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("directory API helpers", () => {
  it("builds the query string (repeated filters, archived, sort, columns)", () => {
    const query = new URLSearchParams(
      directoryQuery({
        practice: PRACTICE,
        q: " maple ",
        filters: { province: ["ON", "QC"], payroll: ["yes"] },
        archived: true,
        sort: ["-overdue", "name"],
        columns: ["bn", "status"],
        facets: false,
      }),
    );
    expect(query.getAll("province")).toEqual(["ON", "QC"]);
    expect(query.get("q")).toBe("maple");
    expect(query.get("archived")).toBe("include");
    expect(query.get("sort")).toBe("-overdue,name");
    expect(query.get("columns")).toBe("bn,status");
    expect(query.get("facets")).toBe("0");
    expect(query.get("page_size")).toBe("2000");
  });

  it("saved view ↔ screen state", () => {
    const state = viewToState(view({ filters: { q: "map", archived: "include", tag: ["A"] } }), []);
    expect(state).toMatchObject({ q: "map", archived: true, filters: { tag: ["A"] } });
    expect(stateToView(state).filters).toEqual({ tag: ["A"], q: "map", archived: "include" });
    expect(sameState(DEFAULT_STATE, { ...DEFAULT_STATE, filters: { province: [] } })).toBe(true);
    expect(formatBn("123456782")).toBe("123 456 782");
  });
});

describe("DirectoryScreen", () => {
  it("lists the organisations with BN, status chips and the summary (T09)", async () => {
    const { lists } = mockApi();
    setup();
    expect(await screen.findByText("Maple Leaf Supply Ltd.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Organisations" })).toBeInTheDocument();
    expect(screen.getByText("2 organisations assigned to Abuodeh CPA")).toBeInTheDocument();
    const [maple, erable] = bodyRows();
    expect(within(maple!).getByText("123 456 782")).toBeInTheDocument();
    expect(within(erable!).getByText("Trial 12 d")).toBeInTheDocument();
    expect(
      within(maple!).getByRole("link", { name: "Open in new tab: Maple Leaf Supply Ltd." }),
    ).toHaveAttribute("target", "_blank");
    const first = lists()[0]!.url;
    expect(first.searchParams.get("practice")).toBe(PRACTICE);
    expect(first.searchParams.get("columns")).toBe("name,bn,province,package,status,fye,overdue");
    expect(screen.getByRole("columnheader", { name: /Organisation/ })).toHaveAttribute(
      "aria-sort",
      "none",
    );
  });

  it("asks the server once, 150 ms after the last key, and highlights matches (T10)", async () => {
    const { lists } = mockApi({
      list: (url) =>
        json(
          page(url.searchParams.get("q") ? [ROWS[0]!] : ROWS, {
            count: url.searchParams.get("q") ? 1 : 2,
          }),
        ),
    });
    setup();
    await screen.findByText("Maple Leaf Supply Ltd.");
    const before = lists().length;
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const search = screen.getByRole("searchbox", { name: "Search organisations" });
    fireEvent.change(search, { target: { value: "1" } });
    fireEvent.change(search, { target: { value: "123" } });
    fireEvent.change(search, { target: { value: "123 456" } });
    act(() => vi.advanceTimersByTime(100));
    expect(lists().length).toBe(before);
    act(() => vi.advanceTimersByTime(60));
    await waitFor(() => expect(lists().length).toBe(before + 1));
    vi.useRealTimers();
    expect(lists().at(-1)!.url.searchParams.get("q")).toBe("123 456");
    await waitFor(() => expect(bodyRows()).toHaveLength(1));
    const marks = Array.from(bodyRows()[0]!.querySelectorAll("mark")).map((m) => m.textContent);
    expect(marks).toEqual(["123 456"]);
    expect(document.querySelector("[data-directory-summary]")).toHaveTextContent(
      "1 of 2 organisations",
    );
  });

  it("filters panel: F opens it, options carry counts, a chip removes the filter (T11)", async () => {
    const { lists } = mockApi();
    const { user } = setup();
    await screen.findByText("Maple Leaf Supply Ltd.");
    await user.keyboard("f");
    const panel = await screen.findByRole("complementary", { name: "Filters" });
    const ontario = within(panel).getByRole("checkbox", { name: /^Ontario ?, 1 organisation$/ });
    expect(within(panel).getByRole("group", { name: "Province" })).toContainElement(ontario);
    await user.click(ontario);
    await waitFor(() =>
      expect(lists().at(-1)!.url.searchParams.getAll("province")).toEqual(["ON"]),
    );
    expect(screen.getByRole("button", { name: "Filters (1)" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Remove filter Province: Ontario" }));
    await waitFor(() => expect(lists().at(-1)!.url.searchParams.getAll("province")).toEqual([]));
    await user.click(within(panel).getByRole("switch", { name: "Show archived organisations" }));
    await waitFor(() => expect(lists().at(-1)!.url.searchParams.get("archived")).toBe("include"));
    await expectNoAxeViolations(document.body);
  });

  it("opens the default view first and saves, updates, renames, deletes views (T12)", async () => {
    const { calls, lists } = mockApi({ views: [view({ is_default: true })] });
    const { user } = setup();
    await waitFor(() => expect(lists().length).toBe(1));
    const first = lists()[0]!.url.searchParams;
    expect(first.getAll("province")).toEqual(["ON"]);
    expect(first.get("sort")).toBe("-overdue");
    expect(first.get("columns")).toBe("name,bn,status");
    const rail = screen.getByRole("navigation", { name: "Saved views" });
    expect(within(rail).getByRole("button", { name: /^Ontario paid/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    expect(await screen.findByText("View “Ontario paid”")).toBeInTheDocument();

    // change it → "(changed)" → Save view updates it on the server
    await user.click(await screen.findByRole("button", { name: "Remove filter Status: Paid" }));
    expect(await screen.findByText("View “Ontario paid” (changed)")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save view" }));
    const patch = await waitFor(() => {
      const found = calls.find((c) => c.init?.method === "PATCH");
      expect(found).toBeTruthy();
      return found!;
    });
    expect(JSON.parse(String(patch.init!.body)).filters).toEqual({ province: ["ON"] });

    // save a new one: a taken name keeps the dialog open with the server's message
    await user.click(within(rail).getByRole("button", { name: "Save current view" }));
    const dialog = await screen.findByRole("dialog", { name: "Save view" });
    await user.type(within(dialog).getByRole("textbox", { name: "View name" }), "Taken");
    await user.click(within(dialog).getByRole("button", { name: "Save view" }));
    expect(
      await within(dialog).findByText("You already have a view called Taken."),
    ).toBeInTheDocument();
    await user.clear(within(dialog).getByRole("textbox", { name: "View name" }));
    await user.type(within(dialog).getByRole("textbox", { name: "View name" }), "Quebec");
    await user.click(within(dialog).getByRole("button", { name: "Save view" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(within(rail).getByRole("button", { name: "Quebec" })).toHaveAttribute(
      "aria-current",
      "true",
    );

    // delete it from its menu, confirmed
    await user.click(within(rail).getByRole("button", { name: "Options for view Quebec" }));
    await user.click(screen.getByRole("button", { name: "Delete…" }));
    const confirm = await screen.findByRole("dialog", { name: "Delete view “Quebec”?" });
    await user.click(within(confirm).getByRole("button", { name: "Delete view" }));
    await waitFor(() => expect(within(rail).queryByRole("button", { name: "Quebec" })).toBeNull());
    expect(calls.some((c) => c.init?.method === "DELETE")).toBe(true);
  });

  it("works without a mouse: / search, ↓ rows, Enter opens, Ctrl/⌘+Enter new tab (T13)", async () => {
    mockApi();
    const { user, navigate, openTab } = setup();
    await screen.findByText("Maple Leaf Supply Ltd.");
    await user.keyboard("/");
    expect(screen.getByRole("searchbox", { name: "Search organisations" })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(bodyRows()[0]).toHaveFocus();
    await user.keyboard("{ArrowDown}{Control>}{Enter}{/Control}");
    expect(openTab).toHaveBeenCalledWith(`/o/${ROWS[1]!.id}/home`);
    await user.keyboard("{Enter}");
    expect(navigate).toHaveBeenCalledWith(`/o/${ROWS[1]!.id}/home`);
  });

  it("first run: no organisations → Create organisation (and Open demo when it exists) (T14)", async () => {
    mockApi({ list: () => json(page([], { total: 0 })) });
    const { user, navigate } = setup({ demoHref: "/demo" });
    expect(
      await screen.findByRole("heading", { name: "Your practice has no organisations yet" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Open demo" }));
    expect(navigate).toHaveBeenCalledWith("/demo");
    await user.click(screen.getByRole("button", { name: "Create organisation" }));
    const dialog = await screen.findByRole("dialog", { name: "New organisation" });
    expect(within(dialog).getByRole("textbox", { name: "Organisation name" })).toHaveFocus();
    await expectNoAxeViolations(document.body);
  });

  it("no results: says so and clears the search and filters (T14)", async () => {
    const { lists } = mockApi({
      list: (url) =>
        json(
          page(url.searchParams.get("q") ? [] : ROWS, { count: url.searchParams.get("q") ? 0 : 2 }),
        ),
    });
    const { user } = setup();
    await screen.findByText("Maple Leaf Supply Ltd.");
    await user.type(screen.getByRole("searchbox", { name: "Search organisations" }), "zz");
    expect(
      await screen.findByRole("heading", { name: "No organisations match" }),
    ).toBeInTheDocument();
    const state = document.querySelector<HTMLElement>("[data-grid-state=no-results]")!;
    await user.click(within(state).getByRole("button", { name: "Clear search and filters" }));
    await waitFor(() => expect(lists().at(-1)!.url.searchParams.get("q")).toBeNull());
  });

  it("error: says the directory didn't load; Try again asks again (T14)", async () => {
    let fail = true;
    const { lists } = mockApi({ list: () => (fail ? json({}, 500) : json(page(ROWS))) });
    const { user } = setup();
    expect(
      await screen.findByRole("heading", { name: "The directory didn't load" }),
    ).toBeInTheDocument();
    await expectNoAxeViolations(document.body);
    fail = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Maple Leaf Supply Ltd.")).toBeInTheDocument();
    expect(lists().length).toBe(2);
  });

  it("loading: skeleton rows and the announcement (T14)", async () => {
    mockApi({ list: () => new Promise<Response>(() => undefined) });
    setup();
    await waitFor(() => expect(screen.getByRole("grid")).toHaveAttribute("aria-busy", "true"));
    expect(screen.getByText("Loading organisations")).toBeInTheDocument();
  });

  it("is accessible: table semantics, sort state, labelled regions (T15)", async () => {
    mockApi();
    const { user } = setup();
    await screen.findByText("Maple Leaf Supply Ltd.");
    const grid = screen.getByRole("grid", { name: "Organisations" });
    expect(grid).toHaveAttribute("aria-rowcount", "3");
    const header = within(grid).getByRole("columnheader", { name: /Overdue/ });
    await user.click(within(header).getByRole("button"));
    expect(header).toHaveAttribute("aria-sort", "ascending");
    expect(screen.getByRole("navigation", { name: "Saved views" })).toBeInTheDocument();
    await expectNoAxeViolations(document.body);
  });
});
