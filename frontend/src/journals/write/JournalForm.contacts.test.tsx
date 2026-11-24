import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import { JournalForm } from "./JournalForm";

/**
 * C-03-T12 — contact column of the journal lines: hidden by default (a toggle shows it); choosing
 * an account that requires a contact reveals the column and focuses that line's contact cell, and
 * the column can't be hidden while such an account is on a line.
 */
const ORG = "acme";
const AR = "11001100-0000-4000-8000-000000000001";
const OFFICE = "61006100-0000-4000-8000-000000000002";
const CUSTOMER = "c0c0c0c0-0000-4000-8000-000000000003";

const account = (id: string, code: string, name: string, requireContact: boolean) => ({
  id,
  code,
  name,
  type: requireContact ? "asset" : "expense",
  has_children: false,
  require_contact: requireContact,
  require_tracking: false,
  require_attachment: false,
});

let checks: Record<string, unknown>[] = [];

function serve(contactLines: number[] = []) {
  checks = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        if (url.includes("/accounts?"))
          return {
            body: {
              count: 2,
              results: [
                account(AR, "1100", "Accounts receivable", true),
                account(OFFICE, "6100", "Office supplies", false),
              ],
            },
          };
        if (url.includes("/contacts?"))
          return {
            body: {
              count: 1,
              next_offset: null,
              role_counts: {},
              results: [{ id: CUSTOMER, display_name: "Maple Leaf Ltd", roles: ["customer"] }],
            },
          };
        if (url.endsWith("/journals/check")) {
          checks.push(JSON.parse(String(init?.body)) as Record<string, unknown>);
          return {
            body: {
              ok: true,
              errors: [],
              shortfalls: [],
              adviser: false,
              needs: { attachment: false, contact_lines: contactLines },
            },
          };
        }
        return { status: 404, body: {} };
      }),
    ),
  );
}

afterEach(() => vi.unstubAllGlobals());

it("hides the contact column by default; the toggle shows and hides it", async () => {
  serve();
  renderWithIntl(<JournalForm org={ORG} />);
  await screen.findAllByRole("option", { name: /Office supplies/ });
  expect(screen.queryByRole("columnheader", { name: "Contact" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Show contact column" }));
  expect(screen.getByRole("columnheader", { name: "Contact" })).toBeVisible();
  expect(await screen.findAllByRole("option", { name: "Maple Leaf Ltd" })).toHaveLength(2);
  await userEvent.click(screen.getByRole("button", { name: "Hide contact column" }));
  expect(screen.queryByRole("columnheader", { name: "Contact" })).toBeNull();
});

it("a require-contact account reveals the column and focuses that line's contact cell", async () => {
  serve();
  renderWithIntl(<JournalForm org={ORG} />);
  await screen.findAllByRole("option", { name: /Office supplies/ });
  await userEvent.selectOptions(screen.getByLabelText("Account, line 2"), AR);
  const cell = await screen.findByLabelText("Contact, line 2");
  await waitFor(() => expect(cell).toHaveFocus());
  expect(cell).toHaveAttribute("aria-required", "true");
  expect(cell).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByText("This account needs a contact.")).toBeVisible();
  // Line 1 has no such account: its cell is there (the column is) but not required.
  expect(screen.getByLabelText("Contact, line 1")).not.toHaveAttribute("aria-required");
  // While the account needs a contact, the column can't be hidden.
  expect(screen.getByRole("button", { name: "Hide contact column" })).toBeDisabled();

  await screen.findAllByRole("option", { name: "Maple Leaf Ltd" });
  await userEvent.selectOptions(cell, CUSTOMER);
  expect(cell).not.toHaveAttribute("aria-invalid");
  expect(screen.queryByText("This account needs a contact.")).toBeNull();
});

it("sends the chosen contact with the line", async () => {
  serve();
  renderWithIntl(<JournalForm org={ORG} />);
  await screen.findAllByRole("option", { name: /Office supplies/ });
  await userEvent.selectOptions(screen.getByLabelText("Account, line 1"), OFFICE);
  await userEvent.type(screen.getByLabelText("Debit, line 1"), "50");
  await userEvent.selectOptions(screen.getByLabelText("Account, line 2"), AR);
  await userEvent.type(screen.getByLabelText("Credit, line 2"), "50");
  await screen.findAllByRole("option", { name: "Maple Leaf Ltd" });
  await userEvent.selectOptions(screen.getByLabelText("Contact, line 2"), CUSTOMER);
  await waitFor(() => {
    const last = checks.at(-1) as { lines: { contact: string | null }[] } | undefined;
    expect(last?.lines.map((line) => line.contact)).toEqual([null, CUSTOMER]);
  });
});

it("shows the column when the server says a line needs a contact (expense rule)", async () => {
  // The expense-contact rule (C-03-T06) is the organisation's: only the check knows it.
  serve([1]);
  renderWithIntl(<JournalForm org={ORG} />);
  await screen.findAllByRole("option", { name: /Office supplies/ });
  await userEvent.selectOptions(screen.getByLabelText("Account, line 1"), OFFICE);
  await userEvent.type(screen.getByLabelText("Debit, line 1"), "50");
  await userEvent.selectOptions(screen.getByLabelText("Account, line 2"), OFFICE);
  await userEvent.type(screen.getByLabelText("Credit, line 2"), "50");
  const cell = await screen.findByLabelText("Contact, line 1", {}, { timeout: 2000 });
  expect(cell).toHaveAttribute("aria-required", "true");
  expect(screen.getByLabelText("Contact, line 2")).not.toHaveAttribute("aria-required");
});
