import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import type { Journal } from "./api";
import { JournalActions } from "./JournalActions";

/** C-04-T10 — the actions bar on the journal page follows the state matrix. */
const journal = (over: Partial<Journal>): Journal => ({
  id: "j1",
  number: "JE-000042",
  date: "2026-06-30",
  type: "manual",
  status: "posted",
  narration: "Accrual",
  source: null,
  book_scope: "both",
  total: "100.00",
  lines: [],
  books: {},
  reversal_of: null,
  reversed_by: null,
  posted_by: null,
  posted_at: null,
  audit: [],
  viewer: { is_author: false, can_approve: false, blocked: "not_waiting" },
  ...over,
});

let calls: { url: string; body: unknown }[] = [];
beforeEach(() => {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        if (url.endsWith("/my-permissions"))
          return { body: { permissions: ["accounting.journals.post"] } };
        calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null });
        return { status: 201, body: journal({ id: "j2", status: "posted" }) };
      }),
    ),
  );
});
afterEach(() => vi.unstubAllGlobals());

const names = () =>
  Array.from(document.querySelectorAll("[data-action]")).map((el) =>
    el.getAttribute("data-action"),
  );

it("posted manual journal: Copy and Reverse (with its date)", async () => {
  const done = vi.fn();
  renderWithIntl(<JournalActions org="acme" journal={journal({})} onDone={done} />);
  await waitFor(() => expect(names()).toEqual(["copy", "reverse"]));
  expect(screen.getByRole("link", { name: "Copy journal" })).toHaveAttribute(
    "href",
    "/o/acme/accounting/journals/new?copy=j1",
  );
  await userEvent.click(screen.getByRole("button", { name: "Reverse journal" }));
  const dialog = await screen.findByRole("dialog", { name: "Reverse this journal?" });
  expect(dialog).toBeVisible();
  const field = screen.getByLabelText("Reversal date");
  await userEvent.clear(field);
  await userEvent.type(field, "2026-07-01");
  await userEvent.click(screen.getAllByRole("button", { name: "Reverse journal" }).at(-1)!);
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(calls[0]).toEqual({
    url: "/api/v1/o/acme/journals/j1/reverse",
    body: { date: "2026-07-01" },
  });
});

it("awaiting approval, the author: Withdraw and Copy, never Approve — 'You created this'", async () => {
  renderWithIntl(
    <JournalActions
      org="acme"
      journal={journal({
        status: "awaiting_approval",
        viewer: { is_author: true, can_approve: false, blocked: "self" },
      })}
      onDone={() => undefined}
    />,
  );
  await waitFor(() => expect(names()).toEqual(["withdraw", "copy"]));
  expect(screen.getByText("You created this: someone else must approve it.")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Approve and post" })).toBeNull();
});

it("awaiting approval, an approver: Approve and Send back (with a reason)", async () => {
  renderWithIntl(
    <JournalActions
      org="acme"
      journal={journal({
        status: "awaiting_approval",
        viewer: { is_author: false, can_approve: true, blocked: null },
      })}
      onDone={() => undefined}
    />,
  );
  await waitFor(() => expect(names()).toEqual(["approve", "reject", "copy"]));
  await userEvent.click(screen.getByRole("button", { name: "Send back" }));
  const send = screen.getAllByRole("button", { name: "Send back" }).at(-1)!;
  expect(send).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Reason (at least 3 characters)"), "Wrong account");
  await userEvent.click(send);
  await waitFor(() => expect(calls[0]?.url).toBe("/api/v1/o/acme/journals/j1/reject"));
  expect(calls[0]?.body).toEqual({ reason: "Wrong account" });
});

it("a journal posted by a module has no actions", async () => {
  const { container } = renderWithIntl(
    <JournalActions org="acme" journal={journal({ type: "sales" })} onDone={() => undefined} />,
  );
  await new Promise((resolve) => setTimeout(resolve, 20));
  expect(container.querySelector("[data-journal-actions]")).toBeNull();
});
