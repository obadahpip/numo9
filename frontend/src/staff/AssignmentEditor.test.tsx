import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { resetCsrfToken } from "@/auth/client";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import type { Assignments } from "./api";
import { AssignmentEditor } from "./AssignmentEditor";

/**
 * V-05-T04 — assignment editor UI: add an organisation by search, assign a group with a role,
 * remove; each change saved at once (the API grants the access on the next request:
 * backend/tests/test_staff_assignments.py).
 */

let state: Assignments = { organisations: [], groups: [] };
const calls: { method: string; url: string; body?: unknown }[] = [];

beforeEach(() => {
  resetCsrfToken();
  calls.length = 0;
  state = { organisations: [{ id: "o1", name: "Maple Leaf Supply" }], groups: [] };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      const json = (data: unknown) =>
        new Response(JSON.stringify(data), { headers: { "Content-Type": "application/json" } });
      if (url.includes("auth/csrf")) return json({ csrfToken: "t" });
      if (url.includes("/practice/groups"))
        return json({
          practice: "p",
          groups: [
            {
              id: "g1",
              name: "Toronto office",
              parent: null,
              depth: 1,
              has_children: false,
              organisation_count: 3,
              subtree_organisation_count: 3,
              staff_count: 0,
            },
          ],
        });
      if (url.includes("/practice/orgs"))
        return json({ results: [{ id: "o2", name: "Birch Holdings" }], count: 1 });
      if (method === "PUT" && url.includes("/organisations/o2"))
        state = {
          ...state,
          organisations: [...state.organisations, { id: "o2", name: "Birch Holdings" }],
        };
      if (method === "DELETE" && url.includes("/organisations/o1"))
        state = { ...state, organisations: state.organisations.filter((o) => o.id !== "o1") };
      if (method === "PUT" && url.includes("/groups/g1"))
        state = {
          ...state,
          groups: [{ id: "g1", name: "Toronto office", role: "reviewer", depth: 1 }],
        };
      return json(state);
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());

it("adds and removes organisations and groups", async () => {
  const user = userEvent.setup();
  const { container } = renderWithIntl(
    <AssignmentEditor practice="p" user={{ id: "u1", name: "Sam Patel" }} />,
  );
  expect(await screen.findByRole("heading", { name: "Sam Patel works on" })).toBeVisible();
  await user.type(screen.getByLabelText("Add an organisation"), "Birch");
  await user.click(await screen.findByRole("button", { name: "Add Birch Holdings" }));
  expect(calls.find((c) => c.method === "PUT")?.url).toBe(
    "/api/v1/practice/staff/u1/organisations/o2?practice=p",
  );
  expect(await screen.findByRole("button", { name: "Remove Birch Holdings" })).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Remove Maple Leaf Supply" }));
  expect(await screen.findByText("Birch Holdings")).toBeVisible();
  expect(screen.queryByText("Maple Leaf Supply")).toBeNull();

  await user.selectOptions(screen.getByLabelText("Group"), "g1");
  await user.selectOptions(screen.getByLabelText("Role in the group"), "reviewer");
  await user.click(screen.getByRole("button", { name: "Assign to group" }));
  const put = calls.filter((c) => c.method === "PUT").at(-1);
  expect(put?.body).toEqual({ role: "reviewer" });
  const groups = await screen.findByText("Toronto office · Reviewer");
  expect(within(groups.closest("li") as HTMLElement).getByRole("button")).toHaveAccessibleName(
    "Remove Toronto office",
  );
  await expectNoAxeViolations(container);
});
