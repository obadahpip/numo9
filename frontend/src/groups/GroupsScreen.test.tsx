import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { moveTargets, type Group } from "./api";
import { GroupsScreen } from "./GroupsScreen";

/**
 * V-02-T09 — group tree with drag and drop + keyboard "Move to…". Acceptance: move works by
 * keyboard (focus the tree with Tab, ↓ to a group, Move to…, arrows in the radio group, Enter);
 * dragging a group onto another moves it under it; the tree has no axe violations. The moves go
 * to `PATCH /api/v1/practice/groups/<id>` with the new parent.
 */

const PRACTICE = "6ca1b880-64f7-4053-80e3-0c3618895553";

function group(id: string, name: string, depth: number, parent: string | null): Group {
  return {
    id,
    name,
    parent,
    depth,
    has_children: false,
    organisation_count: 1,
    subtree_organisation_count: 2,
    staff_count: 1,
  };
}

const GROUPS: Group[] = [
  { ...group("ott", "Ottawa office", 1, null) },
  { ...group("tor", "Toronto office", 1, null), has_children: true },
  group("ret", "Retail clients", 2, "tor"),
];

function mockApi() {
  const patches: { id: string; body: unknown }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = new URL(String(input), "http://numo9.test");
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    if (url.pathname.endsWith("/csrf")) return json({ csrfToken: "t" });
    if (url.pathname === "/api/v1/practice/groups")
      return json({ practice: PRACTICE, groups: GROUPS });
    if (init?.method === "PATCH") {
      const body = JSON.parse(String(init.body)) as { parent: string | null };
      patches.push({ id: url.pathname.split("/").pop()!, body });
      if (body.parent === "ret")
        return json(
          { detail: "Groups can be 5 levels deep at most.", code: "workspace.group.too_deep" },
          400,
        );
      return json(GROUPS[0]);
    }
    return json({}, 404);
  });
  return patches;
}

afterEach(() => vi.restoreAllMocks());

it("move targets leave out the group, its sub-groups and its current parent", () => {
  const targets = moveTargets(GROUPS, GROUPS[1]!).map((g) => g?.name ?? "top");
  expect(targets).toEqual(["Ottawa office"]); // already top level: Toronto can go under Ottawa
  expect(moveTargets(GROUPS, GROUPS[2]!).map((g) => g?.name ?? "top")).toEqual([
    "top",
    "Ottawa office",
  ]);
});

it("moves a group with the keyboard only", async () => {
  const patches = mockApi();
  const user = userEvent.setup();
  const { container } = renderWithIntl(<GroupsScreen practice={PRACTICE} />);
  const tree = await screen.findByRole("tree", { name: "Practice groups" });
  const items = within(tree).getAllByRole("treeitem");
  expect(items.map((i) => i.getAttribute("aria-level"))).toEqual(["1", "1", "2"]);
  items[0]!.focus();
  await user.keyboard("{ArrowDown}{ArrowDown}");
  expect(items[2]).toHaveFocus();
  await user.tab(); // into the row: Add sub-group, Rename, Move to…
  await user.tab();
  await user.tab();
  expect(screen.getByRole("button", { name: "Move Retail clients to…" })).toHaveFocus();
  await user.keyboard("{Enter}");
  const dialog = await screen.findByRole("dialog", { name: "Move Retail clients" });
  const top = within(dialog).getByRole("radio", { name: "Top level" });
  expect(top).toBeChecked();
  within(dialog).getByRole("radio", { name: "Ottawa office" }).focus();
  await user.keyboard(" "); // Space chooses the focused option
  expect(within(dialog).getByRole("radio", { name: "Ottawa office" })).toBeChecked();
  within(dialog).getByRole("button", { name: "Move" }).focus();
  await user.keyboard("{Enter}");
  await waitFor(() => expect(patches).toEqual([{ id: "ret", body: { parent: "ott" } }]));
  await waitFor(() =>
    expect(screen.getByRole("status")).toHaveTextContent("Retail clients moved."),
  );
  await expectNoAxeViolations(container);
});

it("moves a group by dragging it onto another, and shows a refusal", async () => {
  const patches = mockApi();
  renderWithIntl(<GroupsScreen practice={PRACTICE} />);
  const tree = await screen.findByRole("tree");
  const [ottawa, toronto, retail] = within(tree).getAllByRole("treeitem");
  const data = new Map<string, string>();
  const dataTransfer = {
    setData: (k: string, v: string) => data.set(k, v),
    getData: (k: string) => data.get(k) ?? "",
    effectAllowed: "",
  };
  fireEvent.dragStart(ottawa!, { dataTransfer });
  fireEvent.dragOver(toronto!, { dataTransfer });
  fireEvent.drop(toronto!, { dataTransfer });
  await waitFor(() => expect(patches).toEqual([{ id: "ott", body: { parent: "tor" } }]));
  fireEvent.dragStart(toronto!, { dataTransfer });
  fireEvent.dragOver(retail!, { dataTransfer });
  fireEvent.drop(retail!, { dataTransfer });
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Groups can be 5 levels deep at most.",
  );
});
