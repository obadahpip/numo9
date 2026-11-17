import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { directoryQuery, type DirectoryPage, type DirectoryRow } from "./api";
import { DirectoryScreen } from "./DirectoryScreen";

/**
 * V-02-T08 — directory "group by" + group filter + tag filter. Acceptance: group-by headers show
 * counts — the server's `grouping` count per group, in tree order, then "No group"; the group
 * filter lists the practice's groups (indented by level) with their facet counts; rows carry
 * their group badges.
 */

const PRACTICE = "6ca1b880-64f7-4053-80e3-0c3618895553";
const TORONTO = "11111111-1111-4111-8111-111111111111";
const RETAIL = "22222222-2222-4222-8222-222222222222";

const rows: DirectoryRow[] = [
  { id: "a", name: "Maple Leaf Supply Ltd.", groups: [{ id: TORONTO, name: "Toronto office" }] },
  { id: "b", name: "Érable Bakery Inc.", groups: [{ id: RETAIL, name: "Retail clients" }] },
  { id: "c", name: "Lone Pine Ltd.", groups: [] },
];

function page(grouped: boolean): DirectoryPage {
  return {
    practice: { id: PRACTICE, name: "Abuodeh CPA" },
    count: 3,
    total: 3,
    page: 1,
    page_size: 2000,
    pages: 1,
    columns: [],
    results: rows,
    facets: {
      package: [],
      status: [],
      province: [],
      fye: [],
      gst_cycle: [],
      payroll: [],
      overdue: [],
      unfiled: [],
      tag: [{ value: "VIP", label: "VIP", count: 1 }],
      group: [
        { value: TORONTO, label: "Toronto office", count: 2, depth: 1 },
        { value: RETAIL, label: "Retail clients", count: 1, depth: 2 },
      ],
    },
    ...(grouped
      ? {
          grouping: [
            {
              group: { id: TORONTO, name: "Toronto office", depth: 1, parent: null },
              count: 1,
              organisations: ["a"],
            },
            {
              group: { id: RETAIL, name: "Retail clients", depth: 2, parent: TORONTO },
              count: 1,
              organisations: ["b"],
            },
            { group: null, count: 1, organisations: ["c"] },
          ],
        }
      : {}),
  };
}

function mockApi() {
  const lists: URL[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = new URL(String(input), "http://numo9.test");
    const json = (body: unknown) =>
      new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
    if (url.pathname.endsWith("/csrf")) return json({ csrfToken: "t" });
    if (url.pathname === "/api/v1/practice/views") return json([]);
    if (url.pathname === "/api/v1/practice/orgs") {
      lists.push(url);
      return json(page(url.searchParams.get("group_by") === "group"));
    }
    return json({});
  });
  return lists;
}

afterEach(() => vi.restoreAllMocks());

it("asks for group_by=group", () => {
  const query = new URLSearchParams(
    directoryQuery({ practice: PRACTICE, groupBy: "group", filters: { group: [TORONTO] } }),
  );
  expect(query.get("group_by")).toBe("group");
  expect(query.getAll("group")).toEqual([TORONTO]);
});

it("groups the directory with a header and count per group", async () => {
  const lists = mockApi();
  const user = userEvent.setup();
  const { container } = renderWithIntl(<DirectoryScreen practice={PRACTICE} />);
  await screen.findByText("Maple Leaf Supply Ltd.");
  const choice = screen.getByRole("group", { name: "Group by" });
  await user.click(within(choice).getByRole("button", { name: "Group" }));
  expect(within(choice).getByRole("button", { name: "Group" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await waitFor(() => expect(lists.at(-1)?.searchParams.get("group_by")).toBe("group"));
  const headers = await screen.findAllByRole("button", { name: /^Show or hide/ });
  expect(headers.map((h) => h.textContent)).toEqual([
    "Toronto office — 1 organisation",
    "Retail clients — 1 organisation",
    "No group — 1 organisation",
  ]);
  const retail = container.querySelector(`[data-group-section="${RETAIL}"]`) as HTMLElement;
  expect(within(retail).getByText("Érable Bakery Inc.")).toBeInTheDocument();
  expect(within(retail).queryByText("Maple Leaf Supply Ltd.")).toBeNull();
  await user.click(headers[1]!);
  expect(headers[1]).toHaveAttribute("aria-expanded", "false");
  await expectNoAxeViolations(container);
});

it("offers the practice's groups as a filter, indented by level", async () => {
  mockApi();
  const user = userEvent.setup();
  const { container } = renderWithIntl(<DirectoryScreen practice={PRACTICE} />);
  await screen.findByText("Maple Leaf Supply Ltd.");
  await user.click(screen.getByRole("button", { name: "Filters" }));
  const groups = container.querySelector('[data-facet="group"]') as HTMLElement;
  expect(within(groups).getByText("Groups")).toBeInTheDocument();
  const retail = groups.querySelector(`[data-option="${RETAIL}"]`) as HTMLElement;
  expect(retail.getAttribute("data-count")).toBe("1");
  expect(retail.style.paddingInlineStart).toBe("0.75rem");
  expect(within(groups).getByRole("checkbox", { name: /Toronto office/ })).toBeInTheDocument();
});
