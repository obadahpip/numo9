import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import type { ApprovalItem } from "./api";
import { ApprovalsInbox } from "./ApprovalsInbox";

/**
 * C-04-T12 — approvals inbox: list with a side preview and the limit indicator; A approves and
 * R sends back from the keyboard; self-created items say "You created this" with no Approve.
 */
const item = (over: Partial<ApprovalItem>): ApprovalItem => ({
  kind: "journal",
  id: "j1",
  title: "Kingsway lease",
  subtitle: "",
  amount: "2400.00",
  date: "2026-06-30",
  url: "/o/acme/accounting/journals/j1",
  submitted_by: { id: "u1", name: "Ava" },
  submitted_at: "2026-06-30T12:00:00Z",
  created_by: { id: "u1", name: "Ava" },
  can_approve: true,
  blocked: null,
  limit: "5000.00",
  ...over,
});

let results: ApprovalItem[] = [];
let actions: { url: string; body: unknown }[] = [];

function serve(items: ApprovalItem[]) {
  results = items;
  actions = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        if (url.endsWith("/approvals"))
          return {
            body: {
              results,
              kinds: [],
              counts: {
                total: results.length,
                can_approve: results.filter((i) => i.can_approve).length,
              },
            },
          };
        if (init?.method === "POST") {
          actions.push({ url, body: JSON.parse(String(init.body)) });
          results = results.filter((i) => !url.includes(`/${i.id}/`));
          return { body: { id: "j1", status: "posted" } };
        }
        if (url.includes("/journals/"))
          return {
            body: {
              id: "j1",
              lines: [
                {
                  line: 1,
                  account: { id: "a", code: "5400", name: "Rent" },
                  debit: "2400.00",
                  credit: "0.00",
                },
                {
                  line: 2,
                  account: { id: "b", code: "1000", name: "Chequing" },
                  debit: "0.00",
                  credit: "2400.00",
                },
              ],
            },
          };
        return { status: 404, body: {} };
      }),
    ),
  );
}
afterEach(() => vi.unstubAllGlobals());

it("lists items with the limit indicator and previews the selected one", async () => {
  serve([
    item({}),
    item({ id: "j2", title: "Equipment", amount: "7500.00", can_approve: false, blocked: "limit" }),
  ]);
  renderWithIntl(<ApprovalsInbox org="acme" />);
  expect(await screen.findByText("Your limit $5,000.00")).toBeVisible();
  const list = screen.getByRole("listbox", { name: "Waiting for approval" });
  expect(within(list).getAllByRole("option")).toHaveLength(2);
  expect(within(list).getByText("Above your limit")).toBeVisible();
  const preview = screen.getByRole("region", { name: "Preview" });
  expect(await within(preview).findByText("5400 · Rent")).toBeVisible();
});

it("A approves the selected item from the keyboard; R asks for a reason", async () => {
  serve([item({}), item({ id: "j2", title: "Insurance" })]);
  renderWithIntl(<ApprovalsInbox org="acme" />);
  const list = await screen.findByRole("listbox", { name: "Waiting for approval" });
  list.focus();
  await userEvent.keyboard("a");
  await waitFor(() => expect(actions[0]?.url).toBe("/api/v1/o/acme/journals/j1/approve"));
  expect(await screen.findByText("Approved and posted.")).toBeVisible();
  await waitFor(() => expect(within(list).getAllByRole("option")).toHaveLength(1));
  list.focus();
  await userEvent.keyboard("r");
  const dialog = await screen.findByRole("dialog", { name: "Send it back?" });
  await userEvent.type(
    within(dialog).getByLabelText("Reason (at least 3 characters)"),
    "Wrong period",
  );
  await userEvent.click(within(dialog).getByRole("button", { name: "Send back" }));
  await waitFor(() =>
    expect(actions[1]).toEqual({
      url: "/api/v1/o/acme/journals/j2/reject",
      body: { reason: "Wrong period" },
    }),
  );
});

it("self-created items: 'You created this', no Approve, A does nothing", async () => {
  serve([item({ can_approve: false, blocked: "self" })]);
  renderWithIntl(<ApprovalsInbox org="acme" />);
  expect(await screen.findByText("You created this")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  screen.getByRole("listbox").focus();
  await userEvent.keyboard("a");
  expect(actions).toEqual([]);
});

it("empty state", async () => {
  serve([]);
  renderWithIntl(<ApprovalsInbox org="acme" />);
  expect(await screen.findByRole("heading", { name: "Nothing waiting for you" })).toBeVisible();
});
