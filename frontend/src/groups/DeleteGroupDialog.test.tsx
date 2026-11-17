import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import type { Group, GroupImpact } from "./api";
import { GroupsScreen } from "./GroupsScreen";

/**
 * V-02-T11 — delete-group dialog with affected org/staff counts. Acceptance: the counts match the
 * API — the dialog shows `GET /api/v1/practice/groups/<id>/impact` (sub-groups, organisations,
 * staff, staff losing access); Delete stays disabled until they're in; confirming sends DELETE and
 * the tree reloads.
 */

const PRACTICE = "6ca1b880-64f7-4053-80e3-0c3618895553";
const TORONTO: Group = {
  id: "tor",
  name: "Toronto office",
  parent: null,
  depth: 1,
  has_children: true,
  organisation_count: 1,
  subtree_organisation_count: 7,
  staff_count: 2,
};
const IMPACT: GroupImpact = {
  groups: 3,
  organisations: 7,
  staff_assignments: 4,
  staff: 3,
  staff_losing_access: 1,
};

function mockApi() {
  let deleted = false;
  const calls: string[] = [];
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => (release = resolve));
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = new URL(String(input), "http://numo9.test");
    const json = (body: unknown, status = 200) =>
      new Response(status === 204 ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    if (url.pathname.endsWith("/csrf")) return json({ csrfToken: "t" });
    calls.push(`${init?.method ?? "GET"} ${url.pathname}`);
    if (url.pathname === "/api/v1/practice/groups")
      return json({ practice: PRACTICE, groups: deleted ? [] : [TORONTO] });
    if (url.pathname.endsWith("/impact")) {
      await gate;
      return json(IMPACT);
    }
    if (init?.method === "DELETE") {
      deleted = true;
      return json(null, 204);
    }
    if (url.pathname === "/api/v1/practice/tags") return json({ practice: PRACTICE, tags: [] });
    return json({}, 404);
  });
  return { calls, release };
}

afterEach(() => vi.restoreAllMocks());

it("shows the API's impact counts, then deletes", async () => {
  const { calls, release } = mockApi();
  const user = userEvent.setup();
  renderWithIntl(<GroupsScreen practice={PRACTICE} />);
  await user.click(await screen.findByRole("button", { name: "Delete Toronto office" }));
  const dialog = await screen.findByRole("dialog", { name: "Delete Toronto office?" });
  const confirm = within(dialog).getByRole("button", { name: "Delete group" });
  expect(confirm).toBeDisabled(); // until the counts are in
  release();
  await within(dialog).findByText("2 sub-groups are deleted with it");
  expect(within(dialog).getByText(/7 organisations leave the group/)).toBeInTheDocument();
  expect(within(dialog).getByText("3 staff lose this group (4 assignments)")).toBeInTheDocument();
  expect(
    within(dialog).getByText("1 staff member loses access to at least one client."),
  ).toBeInTheDocument();
  await expectNoAxeViolations(dialog);
  await user.click(confirm);
  await waitFor(() => expect(calls).toContain("DELETE /api/v1/practice/groups/tor"));
  expect(
    await screen.findByText("No groups yet. Create one to organise your clients."),
  ).toBeVisible();
});
