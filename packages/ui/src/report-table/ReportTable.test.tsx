import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import { ReportTable, visibleWindow, type ReportTableRow } from "./ReportTable";

/**
 * K-01-T13 — report table: sticky header and first column, sections/rows/totals/text, ⤢ drill
 * on drillable figures, compact density, notes, windowed rendering for long reports.
 */
const labels = {
  drill: (row: string, column: string) => `Show the lines of ${row}, ${column}`,
  note: "Note:",
};
const columns = [{ key: "p0", label: "2026" }];
const rows: ReportTableRow[] = [
  { key: "section:income", label: "Income", kind: "section", values: [] },
  {
    key: "account:4000",
    label: "4000 · Sales",
    kind: "row",
    level: 1,
    values: ["6200.00"],
    drillable: true,
  },
  { key: "text:0", label: "Sales include the June show.", kind: "text", values: [] },
  {
    key: "account:5400",
    label: "5400 · Rent",
    kind: "row",
    level: 1,
    values: ["-2400.00"],
    drillable: true,
    notes: { p0: "Includes deposit" },
  },
  { key: "net", label: "Net income", kind: "total", values: ["3800.00"] },
];

it("renders the kinds of rows with formatted amounts and is accessible", async () => {
  const { container } = render(
    <ReportTable
      caption="Profit and loss"
      columns={columns}
      rows={rows}
      locale="en-CA"
      labels={labels}
    />,
  );
  const table = screen.getByRole("table", { name: "Profit and loss" });
  expect(within(table).getByRole("rowheader", { name: "Income" })).toBeVisible();
  expect(within(table).getByText("$6,200.00")).toBeVisible();
  expect(within(table).getByText("-$2,400.00")).toBeVisible();
  expect(within(table).getByText("Includes deposit")).toBeVisible();
  expect(within(table).getByText("Sales include the June show.")).toHaveAttribute("colspan", "2");
  expect(container.querySelector('[data-row="net"]')).toHaveAttribute("data-kind", "total");
  expect(within(table).queryByText("–")).toBeNull();
  await expectNoAxeViolations(container);
});

it("drills from a figure; rows without lines have no drill button", async () => {
  const onDrill = vi.fn();
  render(
    <ReportTable
      caption="P&L"
      columns={columns}
      rows={rows}
      locale="en-CA"
      labels={labels}
      onDrill={onDrill}
    />,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Show the lines of 4000 · Sales, 2026" }),
  );
  expect(onDrill).toHaveBeenCalledWith(rows[1], 0);
  expect(screen.queryByRole("button", { name: /Net income/ })).toBeNull();
});

it("accounting style puts negatives in parentheses; French formats", () => {
  const { rerender } = render(
    <ReportTable
      caption="P&L"
      columns={columns}
      rows={rows}
      locale="en-CA"
      labels={labels}
      accounting
    />,
  );
  expect(screen.getByText("($2,400.00)")).toBeVisible();
  rerender(
    <ReportTable caption="P&L" columns={columns} rows={rows} locale="fr-CA" labels={labels} />,
  );
  expect(screen.getByText(/6\s200,00\s\$/)).toBeVisible();
});

it("windows long reports: only the rows in view are rendered", () => {
  const many: ReportTableRow[] = Array.from({ length: 5000 }, (_, i) => ({
    key: `account:${i}`,
    label: `Account ${i}`,
    kind: "row",
    values: ["1.00"],
  }));
  const { container } = render(
    <ReportTable
      caption="GL"
      columns={columns}
      rows={many}
      locale="en-CA"
      labels={labels}
      maxHeight={400}
    />,
  );
  const rendered = container.querySelectorAll("tbody tr[data-row]");
  expect(rendered.length).toBeLessThan(100);
  expect(container.querySelector("[data-windowed]")).not.toBeNull();
  const region = screen.getByRole("region", { name: "GL" });
  region.scrollTop = 40 * 2500;
  fireEvent.scroll(region);
  expect(screen.getByText("Account 2500")).toBeInTheDocument();
  expect(screen.queryByText("Account 0")).toBeNull();
});

it("computes the visible window with overscan", () => {
  expect(visibleWindow(1000, 0, 400, 40, 5)).toEqual([0, 15]);
  expect(visibleWindow(1000, 4000, 400, 40, 5)).toEqual([95, 115]);
  expect(visibleWindow(10, 4000, 400, 40, 5)).toEqual([10, 10]);
});
