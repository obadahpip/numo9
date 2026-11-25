import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import type { Criteria, Match } from "./api";
import { ConditionBuilder } from "./ConditionBuilder";
import { emptyRows, newRow, serialise, type Row } from "./conditions";

/**
 * C-07-T10 — condition builder: All / Any, a typed value input per field (account choices, date
 * pickers, amount boxes, fixed choices, tracking pairs, no value for "is empty"); the builder's
 * rows serialise to the API search schema `{match, conditions: [{field, op, value}]}`.
 */
const ACCOUNTS = [
  { id: "acc-office", label: "6100 · Office supplies" },
  { id: "acc-rent", label: "6200 · Rent" },
];

function Harness({ onChange }: { onChange: (criteria: Criteria, rows: Row[]) => void }) {
  const [match, setMatch] = useState<Match>("all");
  const [rows, setRows] = useState<Row[]>([newRow("account")]);
  const report = (m: Match, r: Row[]) => onChange(serialise(m, r), r);
  return (
    <ConditionBuilder
      match={match}
      rows={rows}
      accounts={ACCOUNTS}
      onMatchChange={(m) => {
        setMatch(m);
        report(m, rows);
      }}
      onRowsChange={(r) => {
        setRows(r);
        report(match, r);
      }}
    />
  );
}

function rowAt(index: number) {
  return screen.getByRole("listitem", { name: `Condition ${index + 1}` });
}

test("serialises typed values to the API schema", async () => {
  const user = userEvent.setup();
  let last: Criteria = { match: "all", conditions: [] };
  const { container } = renderWithIntl(<Harness onChange={(c) => (last = c)} />);

  // account: a choice of the chart's accounts
  await user.selectOptions(within(rowAt(0)).getByLabelText("Value"), "acc-office");
  expect(last.conditions).toEqual([{ field: "account", op: "is", value: "acc-office" }]);

  // a date range takes two date inputs
  await user.click(screen.getByRole("button", { name: "Add condition" }));
  await user.selectOptions(within(rowAt(1)).getByLabelText("Field"), "date");
  await user.selectOptions(within(rowAt(1)).getByLabelText("Operator"), "between");
  const dates = within(rowAt(1)).getAllByDisplayValue("");
  expect(dates.map((d) => d.getAttribute("type"))).toEqual(["date", "date"]);
  await user.type(dates[0]!, "2026-01-01");
  await user.type(within(rowAt(1)).getByLabelText("and"), "2026-03-31");

  // amount: numeric box
  await user.click(screen.getByRole("button", { name: "Add condition" }));
  await user.selectOptions(within(rowAt(2)).getByLabelText("Field"), "amount");
  await user.selectOptions(within(rowAt(2)).getByLabelText("Operator"), "gte");
  const amount = within(rowAt(2)).getByLabelText("Value");
  expect(amount).toHaveAttribute("inputmode", "decimal");
  await user.type(amount, "100.50");

  // tax code "is one of" — comma separated, sent as a list
  await user.click(screen.getByRole("button", { name: "Add condition" }));
  await user.selectOptions(within(rowAt(3)).getByLabelText("Field"), "tax_code");
  await user.selectOptions(within(rowAt(3)).getByLabelText("Operator"), "in");
  await user.type(within(rowAt(3)).getByLabelText("Value"), "sales.ON.standard, sales.ON.zero");

  // tracking: category + option
  await user.click(screen.getByRole("button", { name: "Add condition" }));
  await user.selectOptions(within(rowAt(4)).getByLabelText("Field"), "tracking");
  await user.type(within(rowAt(4)).getByLabelText("Category"), "region");
  await user.type(within(rowAt(4)).getByLabelText("Option"), "east");

  // contact is empty: no value input
  await user.click(screen.getByRole("button", { name: "Add condition" }));
  await user.selectOptions(within(rowAt(5)).getByLabelText("Field"), "contact");
  await user.selectOptions(within(rowAt(5)).getByLabelText("Operator"), "empty");
  expect(within(rowAt(5)).queryByLabelText("Value")).toBeNull();

  // book: fixed choices
  await user.click(screen.getByRole("button", { name: "Add condition" }));
  await user.selectOptions(within(rowAt(6)).getByLabelText("Field"), "book");
  await user.selectOptions(within(rowAt(6)).getByLabelText("Value"), "tax");

  await user.selectOptions(screen.getByLabelText("Find lines matching"), "any");
  expect(last).toEqual({
    match: "any",
    conditions: [
      { field: "account", op: "is", value: "acc-office" },
      { field: "date", op: "between", value: { from: "2026-01-01", to: "2026-03-31" } },
      { field: "amount", op: "gte", value: "100.50" },
      { field: "tax_code", op: "in", value: ["sales.ON.standard", "sales.ON.zero"] },
      { field: "tracking", op: "is", value: { region: "east" } },
      { field: "contact", op: "empty", value: null },
      { field: "book", op: "is", value: "tax" },
    ],
  });
  await expectNoAxeViolations(container);
});

test("removing a row and incomplete rows", async () => {
  const user = userEvent.setup();
  let rows: Row[] = [];
  renderWithIntl(<Harness onChange={(_c, r) => (rows = r)} />);
  await user.click(screen.getByRole("button", { name: "Add condition" }));
  expect(rows).toHaveLength(2);
  expect(emptyRows(rows)).toHaveLength(2);
  expect(serialise("all", rows).conditions).toEqual([]);
  await user.click(screen.getByRole("button", { name: "Remove condition 1" }));
  expect(rows).toHaveLength(1);
});

test("a changed field starts from its first operator", async () => {
  const user = userEvent.setup();
  renderWithIntl(<Harness onChange={() => undefined} />);
  await user.selectOptions(within(rowAt(0)).getByLabelText("Field"), "reference");
  expect(within(rowAt(0)).getByLabelText("Operator")).toHaveValue("contains");
  expect(
    within(within(rowAt(0)).getByLabelText("Operator"))
      .getAllByRole("option")
      .map((o) => o.textContent),
  ).toEqual(["contains"]);
});
