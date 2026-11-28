import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import type { RegisterRow } from "./api";
import { BankAccountDetail } from "./BankAccountDetail";
import { bankAccount, ORG, serveJson as serveAll } from "./fixtures";

/** The account page also loads its statement lines and import history (F-02-T13): none here. */
const serveJson: typeof serveAll = (handler) =>
  serveAll((url, init) => {
    if (url.includes("/statement-lines"))
      return {
        body: {
          counts: { all: 0, uncoded: 0, coded: 0, matched: 0, ignored: 0 },
          count: 0,
          results: [],
        },
      };
    if (url.endsWith("/imports")) return { body: { results: [] } };
    return handler(url, init);
  });

/**
 * F-01-T11 — account detail: running balance of the last row = ledger balance; filters sent to
 * the server (true balances kept there); export links carry the filters; empty state.
 */
afterEach(() => vi.unstubAllGlobals());

const ID = "6ca1b880-64f7-4053-80e3-0c3618895553";
const row = (over: Partial<RegisterRow>): RegisterRow => ({
  id: "r",
  date: "2026-06-01",
  journal: { id: "j", number: "JE-000001", type: "bank" },
  status: "posted",
  contact: null,
  description: "",
  reference: "",
  transaction: null,
  voided: false,
  received: null,
  spent: null,
  balance: "0.00",
  ...over,
});
const ROWS = [
  row({ id: "r1", received: "1000.00", balance: "1000.00", description: "Owner deposit" }),
  row({
    id: "r2",
    date: "2026-06-05",
    spent: "200.00",
    balance: "800.00",
    contact: { id: "c1", name: "Staples" },
    reference: "INV-77",
  }),
  row({ id: "r3", date: "2026-06-09", spent: "30.00", balance: "770.00", voided: true }),
];

it("lists transactions with the running balance; last row = ledger balance", async () => {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) => {
        urls.push(url);
        const filtered = url.includes("contact=c1");
        return {
          body: {
            account: bankAccount({ id: ID, ledger_balance: "770.00" }),
            results: filtered ? [ROWS[1]] : ROWS,
          },
        };
      }),
    ),
  );
  const user = userEvent.setup();
  renderWithIntl(<BankAccountDetail org={ORG} account={ID} />);
  expect(await screen.findByRole("heading", { name: "TD Business Chequing" })).toBeVisible();
  const grid = screen.getByRole("grid", { name: "Transactions" });
  const rows = within(grid).getAllByRole("row");
  const last = rows[rows.length - 1]!;
  expect(within(last).getByText("$770.00")).toBeVisible();
  expect(screen.getByText("$770.00", { selector: "[data-ledger-balance]" })).toBeVisible();
  expect(within(last).getByText("Voided")).toBeVisible();
  expect(screen.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
    "href",
    `/api/v1/o/${ORG}/bank-accounts/${ID}/register?export=csv`,
  );

  await user.selectOptions(screen.getByLabelText("Contact"), "c1");
  await user.type(screen.getByLabelText("Amount from"), "100");
  await user.click(screen.getByRole("button", { name: "Apply" }));
  expect(await within(grid).findAllByRole("row")).toHaveLength(2);
  expect(urls[urls.length - 1]).toBe(
    `/api/v1/o/${ORG}/bank-accounts/${ID}/register?contact=c1&amount_min=100`,
  );
  expect(screen.getByRole("link", { name: "Export Excel" })).toHaveAttribute(
    "href",
    `/api/v1/o/${ORG}/bank-accounts/${ID}/register?contact=c1&amount_min=100&export=xlsx`,
  );
  expect(screen.getByRole("link", { name: "Spend money" })).toHaveAttribute(
    "href",
    `/o/${ORG}/banking/spend?account=${ID}`,
  );
});

it("shows the empty state when the account has no transaction", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(serveJson(() => ({ body: { account: bankAccount({ id: ID }), results: [] } }))),
  );
  renderWithIntl(<BankAccountDetail org={ORG} account={ID} />);
  expect(await screen.findByRole("heading", { name: "No transactions yet" })).toBeVisible();
});

it("History opens the account's audit trail (F-01-T14): who renamed it, old and new name", async () => {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) => {
        urls.push(url);
        if (url.includes("/audit/records/"))
          return {
            body: {
              record: {
                type: "banking.BankAccount",
                type_label: "Bank account",
                id: ID,
                label: "TD",
              },
              viewer: { time_format: "24h", time_zone: "America/Toronto" },
              next: null,
              results: [
                {
                  id: "e1",
                  at: "2026-06-30T14:00:00Z",
                  action: "banking.bankaccount.updated",
                  action_label: "Edited",
                  actor: {
                    kind: "user",
                    label: "Dana Lee",
                    user: { id: "u1", name: "Dana Lee", email: "dana@refined.ca" },
                    impersonator: null,
                  },
                  record: {
                    type: "banking.BankAccount",
                    type_label: "Bank account",
                    id: ID,
                    label: "TD",
                  },
                  changes: [
                    {
                      field: "display_name",
                      label: "Name",
                      old: "TD Chequing",
                      new: "TD Business Chequing",
                      masked: false,
                    },
                  ],
                },
              ],
            },
          };
        return { body: { account: bankAccount({ id: ID }), results: [] } };
      }),
    ),
  );
  const user = userEvent.setup();
  renderWithIntl(<BankAccountDetail org={ORG} account={ID} />);
  await screen.findByRole("heading", { name: "TD Business Chequing" });
  await user.click(screen.getByRole("button", { name: "History" }));
  const drawer = await screen.findByRole("dialog");
  expect(await within(drawer).findByText("Dana Lee")).toBeVisible();
  expect(within(drawer).getByText("TD Chequing")).toBeVisible();
  expect(urls.some((u) => u.includes(`/audit/records/banking.BankAccount/${ID}`))).toBe(true);
});
