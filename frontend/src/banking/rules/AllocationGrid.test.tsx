import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import type { Account } from "@/accounts/api";
import type { TaxCode } from "@/tax/api";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import { serveJson } from "../fixtures";
import { AllocationGrid, allocationsValid, percentTotal } from "./AllocationGrid";
import type { RuleType } from "./api";
import { emptyAllocation, type AllocationRow } from "./draft";
import { RuleBuilder } from "./RuleBuilder";

/**
 * F-04-T12 — allocation grid: running % total with red/green validation, tax picker filtered by
 * the rule type. Acceptance: Save is disabled until the percentages total 100 %.
 */
const ORG = "refined";

function account(id: string, code: string, name: string, over: Partial<Account> = {}): Account {
  return { id, code, name, is_bank: false, ...over } as Account;
}

function code(id: string, key: string, name: string, side: "sales" | "purchase"): TaxCode {
  return { id, code: key, name, side, archived_at: null, expired: false } as TaxCode;
}

const ACCOUNTS = [
  account("acc-fuel", "5100", "Fuel"),
  account("acc-meals", "5200", "Meals"),
  account("acc-bank", "1000", "TD Chequing", { is_bank: true }),
];
const CODES = [
  code("c1", "purchase.ON.standard", "HST 13 % (purchases)", "purchase"),
  code("c2", "sales.ON.standard", "HST 13 % (sales)", "sales"),
];

afterEach(() => vi.unstubAllGlobals());

function Grid({ type }: { type: RuleType }) {
  const [rows, setRows] = useState<AllocationRow[]>([emptyAllocation()]);
  return (
    <AllocationGrid
      type={type}
      rows={rows}
      accounts={ACCOUNTS}
      taxCodes={CODES}
      onChange={setRows}
    />
  );
}

it("tax picker is filtered by the rule type; bank accounts are not offered", () => {
  const { unmount } = renderWithIntl(<Grid type="spend" />);
  const options = (label: string) =>
    Array.from((screen.getByLabelText(label) as HTMLSelectElement).options).map((o) => o.text);
  expect(options("Line 1: tax code")).toEqual(["No tax", "HST 13 % (purchases)"]);
  expect(options("Line 1: account")).toEqual(["", "5100 · Fuel", "5200 · Meals"]);
  unmount();
  renderWithIntl(<Grid type="receive" />);
  expect(options("Line 1: tax code")).toEqual(["No tax", "HST 13 % (sales)"]);
});

it("running total is red until the percentages total 100 %, then green", async () => {
  const user = userEvent.setup();
  const { container } = renderWithIntl(<Grid type="spend" />);
  await user.selectOptions(screen.getByLabelText("Line 1: account"), "acc-fuel");
  const first = screen.getByLabelText("Line 1: percentage");
  await user.clear(first);
  await user.type(first, "60");
  await user.click(screen.getByRole("button", { name: "Add a line" }));
  await user.selectOptions(screen.getByLabelText("Line 2: account"), "acc-meals");
  await user.type(screen.getByLabelText("Line 2: percentage"), "30");
  const total = screen.getByRole("status");
  expect(total).toHaveTextContent("Total 90 % — the percentages must total 100 %");
  expect(total).toHaveClass("text-fg-danger");
  await user.clear(screen.getByLabelText("Line 2: percentage"));
  await user.type(screen.getByLabelText("Line 2: percentage"), "40");
  expect(total).toHaveTextContent("Total 100 % — ready");
  expect(total).toHaveClass("text-fg-success");
  await user.selectOptions(screen.getByLabelText("Line 2: percentage or fixed amount"), "fixed");
  expect(screen.getByLabelText("Line 2: fixed amount")).toBeVisible();
  expect(total).toHaveTextContent("Total 60 %");
  await expectNoAxeViolations(container);
});

it("validity rules", () => {
  const row = (mode: "percent" | "fixed", value: string): AllocationRow => ({
    ...emptyAllocation(),
    account: "a",
    mode,
    value,
  });
  expect(allocationsValid([row("percent", "60"), row("percent", "30")])).toBe(false);
  expect(allocationsValid([row("fixed", "10"), row("percent", "100")])).toBe(true);
  expect(
    allocationsValid([row("percent", "33.33"), row("percent", "33.33"), row("percent", "33.34")]),
  ).toBe(true);
  expect(allocationsValid([row("fixed", "25.00")])).toBe(true);
  expect(allocationsValid([row("percent", "abc")])).toBe(false);
  expect(allocationsValid([{ ...row("percent", "100"), account: "" }])).toBe(false);
  expect(percentTotal([row("percent", "33.3333"), row("percent", "66.6667")])).toBe(1_000_000);
});

it("the builder's Save is disabled until the total is 100 %", async () => {
  const user = userEvent.setup();
  const posted: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        if (url.endsWith("/bank-rules") && init?.method === "POST") {
          posted.push(JSON.parse(String(init.body)));
          return { status: 201, body: { id: "new" } };
        }
        if (url.endsWith("/bank-rules/preview")) {
          return {
            body: { since: "", days: 90, applies: 0, shadowed: 0, truncated: false, rows: [] },
          };
        }
        if (url.includes("/accounts?")) return { body: { results: ACCOUNTS, count: 3 } };
        if (url.includes("/tax/codes")) return { body: { results: CODES } };
        return { body: { results: [] } };
      }),
    ),
  );
  const navigate = vi.fn();
  renderWithIntl(<RuleBuilder org={ORG} navigate={navigate} />);
  const save = screen.getByRole("button", { name: "Save rule" });
  await user.type(screen.getByLabelText("Rule name"), "Fuel split");
  await user.type(screen.getByLabelText("Condition 1: value"), "PETRO");
  await screen.findByRole("option", { name: "5100 · Fuel" });
  await user.selectOptions(screen.getByLabelText("Line 1: account"), "acc-fuel");
  await user.selectOptions(screen.getByLabelText("Line 1: tax code"), "purchase.ON.standard");
  await user.clear(screen.getByLabelText("Line 1: percentage"));
  await user.type(screen.getByLabelText("Line 1: percentage"), "60");
  await user.click(screen.getByRole("button", { name: "Add a line" }));
  await user.selectOptions(screen.getByLabelText("Line 2: account"), "acc-meals");
  await user.type(screen.getByLabelText("Line 2: percentage"), "30");
  expect(save).toBeDisabled();
  await user.clear(screen.getByLabelText("Line 2: percentage"));
  await user.type(screen.getByLabelText("Line 2: percentage"), "40");
  expect(save).toBeEnabled();
  await user.click(save);
  expect(navigate).toHaveBeenCalledWith(`/o/${ORG}/banking/rules`);
  expect(posted[0]).toMatchObject({
    type: "spend",
    name: "Fuel split",
    conditions: [{ field: "description", operator: "contains", value: "PETRO" }],
    allocations: [
      { account: "acc-fuel", percent: "60", fixed_amount: null, tax_code: "purchase.ON.standard" },
      { account: "acc-meals", percent: "40", fixed_amount: null, tax_code: "" },
    ],
  });
});
