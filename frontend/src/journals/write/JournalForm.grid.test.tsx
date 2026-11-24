import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import { difference, JournalForm } from "./JournalForm";

/**
 * C-04-T09 — journal editor grid: account autocomplete (by code or name), a difference meter
 * ("Out of balance by $12.50"), Post disabled until the difference is $0.00, Tab past the last
 * cell adds a line and moves to its account.
 */
const RENT = "54005400-0000-4000-8000-000000000001";
const BANK = "10001000-0000-4000-8000-000000000002";

const account = (id: string, code: string, name: string, type: string, subtype: string) => ({
  id,
  code,
  name,
  type,
  subtype,
  subtype_label: "",
  system_role: "",
  is_bank: subtype === "bank",
  depth: 1,
  has_children: false,
  require_contact: false,
  require_tracking: false,
  require_attachment: false,
  default_tax_key: "",
});

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) => {
        if (url.includes("/accounts?"))
          return {
            body: {
              count: 2,
              results: [
                account(RENT, "5400", "Rent", "expense", "operating_expense"),
                account(BANK, "1000", "Chequing", "asset", "bank"),
              ],
            },
          };
        if (url.endsWith("/journals/check"))
          return {
            body: {
              ok: true,
              errors: [],
              shortfalls: [],
              adviser: false,
              needs: { attachment: false, contact_lines: [] },
            },
          };
        return { status: 404, body: {} };
      }),
    ),
  );
});
afterEach(() => vi.unstubAllGlobals());

async function pick(line: number, typed: string, name: RegExp) {
  const box = screen.getByRole("combobox", { name: `Account, line ${line}` });
  await userEvent.click(box);
  await userEvent.type(box, typed);
  await userEvent.click(await screen.findByRole("option", { name }));
}

it("the difference meter and Post follow the balance", async () => {
  renderWithIntl(<JournalForm org="acme" />);
  await screen.findByRole("combobox", { name: "Account, line 1" });
  const post = screen.getByRole("button", { name: "Post journal" });
  const meter = () => document.querySelector("[data-difference]");
  expect(meter()).toHaveTextContent("Enter the debits and credits");
  expect(post).toBeDisabled();

  await pick(1, "5400", /Rent/); // by code
  await userEvent.type(screen.getByLabelText("Debit, line 1"), "1250.00");
  await pick(2, "cheq", /Chequing/); // by name
  await userEvent.type(screen.getByLabelText("Credit, line 2"), "1237.50");
  expect(meter()).toHaveTextContent("Out of balance by $12.50");
  expect(meter()).toHaveAttribute("data-difference", "12.50");
  await waitFor(() => expect(post).toBeDisabled());

  await userEvent.clear(screen.getByLabelText("Credit, line 2"));
  await userEvent.type(screen.getByLabelText("Credit, line 2"), "1250.00");
  expect(meter()).toHaveTextContent("Balanced");
  await waitFor(() => expect(post).toBeEnabled());
});

it("Tab past the last cell adds a line and moves to its account", async () => {
  renderWithIntl(<JournalForm org="acme" />);
  await screen.findByRole("combobox", { name: "Account, line 1" });
  expect(screen.queryByRole("combobox", { name: "Account, line 3" })).toBeNull();
  screen.getByLabelText("Description, line 1").focus();
  await userEvent.tab(); // not the last line: an ordinary Tab
  expect(screen.queryByRole("combobox", { name: "Account, line 3" })).toBeNull();
  screen.getByLabelText("Description, line 2").focus();
  await userEvent.tab();
  const added = await screen.findByRole("combobox", { name: "Account, line 3" });
  await waitFor(() => expect(added).toHaveFocus());
  // Shift+Tab goes back, never adds.
  screen.getByLabelText("Description, line 3").focus();
  await userEvent.tab({ shift: true });
  expect(screen.queryByRole("combobox", { name: "Account, line 4" })).toBeNull();
});

it("difference() works in cents", () => {
  const line = (debit: string, credit: string) => ({
    account: "a",
    debit,
    credit,
    book: "both" as const,
    contact: null,
    description: "",
  });
  expect(difference([line("0.10", ""), line("0.20", ""), line("", "0.30")])).toBe(0);
  expect(difference([line("1250", ""), line("", "1237.5")])).toBe(1250);
});
