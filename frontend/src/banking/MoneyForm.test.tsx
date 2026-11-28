import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { ACCOUNTS, ORG, serveJson } from "./fixtures";
import { moneyLines, MoneyForm } from "./MoneyForm";

/**
 * F-01-T10 — spend / receive money: the D-01 grid in bank mode; purchase codes only on spend and
 * sales codes only on receive; the account's default code is filled in; the contact is optional
 * unless a line's account requires one; posting sends the lines with the chosen code's key.
 */
const OFFICE = "61006100-0000-4000-8000-000000000002";
const AR = "11001100-0000-4000-8000-000000000001";
const SALES = "40004000-0000-4000-8000-000000000004";
const HST_P = "cccc0001-0000-4000-8000-000000000001";
const HST_S = "cccc0002-0000-4000-8000-000000000002";

const glAccount = (id: string, code: string, name: string, type: string, over = {}) => ({
  id,
  code,
  name,
  type,
  subtype: type === "expense" ? "operating_expense" : type === "revenue" ? "revenue" : "",
  subtype_label: "",
  system_role: "",
  is_bank: false,
  depth: 1,
  has_children: false,
  require_contact: false,
  require_tracking: false,
  require_attachment: false,
  default_tax_key: "",
  ...over,
});

const taxCode = (id: string, code: string, name: string, side: string) => ({
  id,
  code,
  version: 1,
  name,
  side,
  type: "taxable",
  province: "ON",
  effective_from: "2016-07-01",
  effective_to: null,
  expired: false,
  archived_at: null,
  rate: "13",
  components: [
    { id: `${id}-c`, key: "hst_on", name: "HST", kind: "hst", rate: "13", recoverable_pct: null },
  ],
});

let posted: Record<string, unknown>[] = [];
let codeQueries: string[] = [];
/** F-07-T07: what each POST answers, in order (then 201). */
let answers: { status: number; body: unknown }[] = [];

function serve() {
  posted = [];
  codeQueries = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        if (url.includes("/bank-accounts?")) return { body: { results: ACCOUNTS } };
        if (url.includes("/accounts?"))
          return {
            body: {
              count: 3,
              results: [
                glAccount(OFFICE, "6100", "Office supplies", "expense", {
                  default_tax_key: "purchase.ON.standard",
                }),
                glAccount(AR, "5200", "Subcontractors", "expense", { require_contact: true }),
                glAccount(SALES, "4000", "Sales", "revenue"),
              ],
            },
          };
        if (url.includes("/contacts?"))
          return {
            body: {
              count: 1,
              next_offset: null,
              role_counts: {},
              results: [{ id: "c1", display_name: "Staples", roles: ["supplier"] }],
            },
          };
        if (url.includes("/tax/codes")) {
          codeQueries.push(url);
          // Both sides served on purpose: the grid must still offer only the form's side.
          return {
            body: {
              results: [
                taxCode(HST_P, "purchase.ON.standard", "HST on purchases", "purchase"),
                taxCode(HST_S, "sales.ON.standard", "HST on sales", "sales"),
              ],
            },
          };
        }
        if (url.includes("/bank-transactions/tax-default"))
          return {
            body: {
              code: url.includes("kind=receive") ? "sales.ON.standard" : "purchase.ON.standard",
              name: "HST",
              taxes: [],
            },
          };
        if (url.includes("/calculate")) return { status: 503, body: {} };
        if (url.includes("/tax/resolve")) {
          // G-02-T08: a sale placed in BC without a PST registration.
          const body = JSON.parse(String(init?.body)) as { side: string; lines: unknown[] };
          return {
            body: {
              lines: body.lines.map(() => ({
                key: body.side === "sales" ? "sales.BC.gst" : "purchase.ON.standard",
                tax_code: null,
                source: "place_of_supply",
                auto: true,
                explanation: "tax.pos.gst_unregistered_pst",
                params: { province: "BC" },
                province: "BC",
                flags: [],
                warnings: body.side === "sales" ? ["tax.pos.pst_unregistered"] : [],
              })),
            },
          };
        }
        if (url.endsWith("/bank-transactions") && init?.method === "POST") {
          posted.push(JSON.parse(String(init.body)) as Record<string, unknown>);
          return answers.shift() ?? { status: 201, body: { id: "t1" } };
        }
        return { status: 404, body: {} };
      }),
    ),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  answers = [];
});

async function chooseAccount(name: RegExp) {
  await userEvent.click(screen.getByRole("combobox", { name: "Account, line 1" }));
  await userEvent.click(await screen.findByRole("option", { name }));
}

it("spend: purchase codes only, the account default filled in, posted with its key", async () => {
  serve();
  const navigate = vi.fn();
  renderWithIntl(
    <MoneyForm org={ORG} kind="spend" account={ACCOUNTS[0]?.id} navigate={navigate} />,
  );
  expect(await screen.findByRole("heading", { name: "Spend money" })).toBeVisible();
  await waitFor(() => expect(codeQueries[0]).toContain("side=purchase"));
  // Bank mode: no quantity column.
  expect(screen.queryByRole("columnheader", { name: "Qty" })).toBeNull();

  await chooseAccount(/Office supplies/);
  const tax = screen.getByRole("combobox", { name: "Tax code, line 1" });
  await waitFor(() => expect(tax).toHaveValue("HST on purchases"));
  await userEvent.click(tax);
  const listbox = await screen.findByRole("listbox");
  expect(within(listbox).queryByText(/HST on sales/)).toBeNull();
  await userEvent.keyboard("{Escape}");

  await userEvent.type(screen.getByRole("textbox", { name: "Amount, line 1" }), "113");
  await userEvent.tab();
  const save = screen.getByRole("button", { name: "Record spend" });
  await waitFor(() => expect(save).toBeEnabled());
  await userEvent.click(save);
  await waitFor(() => expect(posted).toHaveLength(1));
  expect(posted[0]).toMatchObject({
    kind: "spend",
    bank_account: ACCOUNTS[0]?.id,
    tax_mode: "exclusive",
    contact: null,
    lines: [{ account: OFFICE, amount: "113.00", tax_code: "purchase.ON.standard" }],
  });
  expect(navigate).toHaveBeenCalledWith(`/o/${ORG}/banking/${ACCOUNTS[0]?.id}`);
});

it("receive: sales side and sales codes only", async () => {
  serve();
  renderWithIntl(<MoneyForm org={ORG} kind="receive" account={ACCOUNTS[0]?.id} />);
  expect(await screen.findByRole("heading", { name: "Receive money" })).toBeVisible();
  await waitFor(() => expect(codeQueries[0]).toContain("side=sales"));
  await chooseAccount(/Sales/);
  await userEvent.click(screen.getByRole("combobox", { name: "Tax code, line 1" }));
  const listbox = await screen.findByRole("listbox");
  expect(within(listbox).queryByText(/HST on purchases/)).toBeNull();
  expect(within(listbox).getByText(/HST on sales/)).toBeInTheDocument();
});

it("a line on an account that requires a contact makes the contact required", async () => {
  serve();
  renderWithIntl(<MoneyForm org={ORG} kind="spend" account={ACCOUNTS[0]?.id} />);
  await screen.findByRole("heading", { name: "Spend money" });
  const paidTo = screen.getByRole("combobox", { name: "Paid to" });
  expect(paidTo).not.toHaveAttribute("aria-required");
  await chooseAccount(/Subcontractors/);
  await userEvent.type(screen.getByRole("textbox", { name: "Amount, line 1" }), "50");
  await userEvent.tab();
  expect(paidTo).toHaveAttribute("aria-required", "true");
  expect(screen.getByText("A line's account needs a contact.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Record spend" })).toBeDisabled();
  await screen.findByRole("option", { name: "Staples" });
  await userEvent.selectOptions(paidTo, "c1");
  expect(screen.getByRole("button", { name: "Record spend" })).toBeEnabled();
});

it("moneyLines keeps lines with an account and an amount; no-tax mode sends no code", () => {
  const codes = [taxCode(HST_P, "purchase.ON.standard", "HST", "purchase")] as never[];
  const line = (over: object) => ({
    id: "x",
    item: "",
    description: "Paper",
    quantity: "1",
    unitPrice: "10",
    discount: "",
    account: OFFICE,
    taxCode: HST_P,
    ...over,
  });
  expect(
    moneyLines([line({}), line({ account: null }), line({ unitPrice: "0" })], codes, "exclusive"),
  ).toEqual([
    { account: OFFICE, amount: "10.00", description: "Paper", tax_code: "purchase.ON.standard" },
  ]);
  expect(moneyLines([line({})], codes, "no_tax")[0]?.tax_code).toBe("");
});

it("receive: the PST warning shows inline and doesn't block (G-02-T08)", async () => {
  serve();
  renderWithIntl(<MoneyForm org={ORG} kind="receive" account={ACCOUNTS[0]?.id} />);
  expect(
    await screen.findByText(
      /Line 1 is a taxable sale into BC, where you aren't registered for its PST/,
    ),
  ).toBeVisible();
  await chooseAccount(/Sales/);
  expect(screen.getByRole("combobox", { name: "Tax code, line 1" })).toBeEnabled();
});

const PETTY_SHORT = {
  account: { id: "g3", label: "1010 Petty Cash" },
  message: "Petty Cash would be −994.17 on 15 Jun 2026",
};

async function recordOfficeSpend() {
  await chooseAccount(/Office supplies/);
  await userEvent.type(screen.getByRole("textbox", { name: "Amount, line 1" }), "994.17");
  await userEvent.tab();
  const save = screen.getByRole("button", { name: "Record spend" });
  await waitFor(() => expect(save).toBeEnabled());
  await userEvent.click(save);
  return save;
}

it("F-07-T07: a warning shows the inline panel with the reason, sent on the next try", async () => {
  serve();
  answers = [
    {
      status: 422,
      body: {
        code: "ledger.journal.override_reason_required",
        detail: "…",
        adviser: true,
        shortfalls: [{ ...PETTY_SHORT, action: "warn" }],
      },
    },
  ];
  renderWithIntl(<MoneyForm org={ORG} kind="spend" account={ACCOUNTS[2]?.id} navigate={vi.fn()} />);
  await screen.findByRole("heading", { name: "Spend money" });
  const save = await recordOfficeSpend();
  const panel = await screen.findByRole("status", {
    name: "This would take a bank or cash account below zero",
  });
  expect(panel).toHaveAttribute("data-negative-balance", "warn");
  expect(panel).toHaveTextContent("Petty Cash would be −994.17 on 15 Jun 2026");
  expect(save).toBeDisabled();
  await userEvent.type(
    within(panel).getByLabelText("Reason for saving it anyway"),
    "Owner tops it up Monday",
  );
  expect(save).toBeEnabled();
  await userEvent.click(save);
  await waitFor(() => expect(posted).toHaveLength(2));
  expect(posted[1]).toMatchObject({ override_reason: "Owner tops it up Monday" });
});

it("F-07-T07: a block shows who can override and a remedy, saving stays off", async () => {
  serve();
  answers = [
    {
      status: 409,
      body: {
        code: "ledger.journal.negative_cash",
        detail: "…",
        adviser: false,
        shortfalls: [{ ...PETTY_SHORT, action: "block" }],
      },
    },
  ];
  const navigate = vi.fn();
  renderWithIntl(
    <MoneyForm org={ORG} kind="spend" account={ACCOUNTS[2]?.id} navigate={navigate} />,
  );
  await screen.findByRole("heading", { name: "Spend money" });
  const save = await recordOfficeSpend();
  const panel = await screen.findByRole("alert");
  expect(panel).toHaveAttribute("data-negative-balance", "block");
  expect(panel).toHaveTextContent("Who can override: your adviser");
  expect(within(panel).queryByLabelText("Reason for saving it anyway")).toBeNull();
  expect(save).toBeDisabled();
  await userEvent.click(within(panel).getByRole("button", { name: "Record money coming in" }));
  expect(navigate).toHaveBeenCalledWith(`/o/${ORG}/banking/receive?account=${ACCOUNTS[2]?.id}`);
});
