import { render, screen, within } from "@testing-library/react";

import {
  hasActivity,
  isEmptyReport,
  ReportTable,
  visibleRows,
  type ReportTableRow,
} from "./ReportTable";

/**
 * K-01-T16 — zero rendering: an empty P&L shows the no-activity hint (never "–"), totals print
 * $0.00, rows with no activity are hidden unless "show zero rows", an empty cell says so.
 */
const labels = {
  drill: (row: string, column: string) => `Show the lines of ${row}, ${column}`,
  note: "Note:",
  noActivity: "No activity in this period",
  noActivityCell: "No activity",
};
const columns = [
  { key: "p0", label: "2026" },
  { key: "p1", label: "2025" },
];

it("an empty P&L shows the hint and $0.00 totals, never a dash", () => {
  const rows: ReportTableRow[] = [
    { key: "section:income", label: "Income", kind: "section", values: [] },
    { key: "account:4000", label: "4000 · Sales", kind: "row", values: [null, "0.00"] },
    { key: "net", label: "Net income", kind: "total", values: [null, null] },
  ];
  const { container } = render(
    <ReportTable
      caption="Profit and loss"
      columns={columns}
      rows={rows}
      locale="en-CA"
      labels={labels}
      emptyActions={<button type="button">Run this financial year</button>}
    />,
  );
  const hint = screen.getByRole("status");
  expect(hint).toHaveTextContent("No activity in this period");
  expect(within(hint).getByRole("button", { name: "Run this financial year" })).toBeVisible();
  expect(screen.queryByText("4000 · Sales")).toBeNull();
  const net = container.querySelector('[data-row="net"]')!;
  expect(within(net as HTMLElement).getAllByText("$0.00")).toHaveLength(2);
  expect(container.textContent).not.toMatch(/[–—]/);
});

it("hides rows without activity unless show zero rows; empty cells say No activity", () => {
  const rows: ReportTableRow[] = [
    { key: "account:4000", label: "4000 · Sales", kind: "row", values: ["100.00", null] },
    { key: "account:4100", label: "4100 · Other income", kind: "row", values: ["0.00", null] },
    { key: "net", label: "Net income", kind: "total", values: ["100.00", null] },
  ];
  const { rerender } = render(
    <ReportTable caption="P&L" columns={columns} rows={rows} locale="en-CA" labels={labels} />,
  );
  expect(screen.queryByText("4100 · Other income")).toBeNull();
  const sales = screen.getByRole("row", { name: /4000 · Sales/ });
  expect(within(sales).getByText("No activity")).toBeVisible();
  expect(screen.queryByRole("status")).toBeNull();
  rerender(
    <ReportTable
      caption="P&L"
      columns={columns}
      rows={rows}
      locale="en-CA"
      labels={labels}
      showZeroRows
    />,
  );
  expect(screen.getByText("4100 · Other income")).toBeVisible();
});

it("the rules as functions", () => {
  expect([
    hasActivity("0.00"),
    hasActivity("-0.00"),
    hasActivity(null),
    hasActivity("0.01"),
  ]).toEqual([false, false, false, true]);
  const rows: ReportTableRow[] = [
    { key: "s", label: "S", kind: "section", values: [] },
    { key: "a", label: "A", kind: "row", values: ["0.00"] },
  ];
  expect(isEmptyReport(rows)).toBe(true);
  expect(visibleRows(rows).map((r) => r.key)).toEqual(["s"]);
  expect(visibleRows(rows, true).map((r) => r.key)).toEqual(["s", "a"]);
});
