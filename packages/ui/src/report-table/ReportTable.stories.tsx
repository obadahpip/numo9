import type { Meta, StoryObj } from "@storybook/react";

import { ReportTable, type ReportTableRow } from "./ReportTable";

/**
 * Report table (K-01-T13): sections, account rows, text blocks, totals, cell notes; a wide
 * comparison scrolls inside the table.
 */
const meta: Meta<typeof ReportTable> = { title: "Data/Report table", component: ReportTable };
export default meta;
type Story = StoryObj<typeof ReportTable>;

const labels = {
  drill: (row: string, column: string) => `Show the lines of ${row}, ${column}`,
  note: "Note:",
};

const rows: ReportTableRow[] = [
  { key: "section:income", label: "Income", kind: "section", values: [] },
  {
    key: "account:4000",
    label: "4000 · Sales",
    kind: "row",
    level: 1,
    values: ["6200.00", "5100.00"],
    drillable: true,
  },
  { key: "text:0", label: "Sales include the June trade show.", kind: "text", values: [] },
  { key: "section:expenses", label: "Expenses", kind: "section", values: [] },
  {
    key: "account:5400",
    label: "5400 · Rent",
    kind: "row",
    level: 1,
    values: ["2400.00", "2400.00"],
    drillable: true,
    notes: { p0: "Includes the June deposit" },
  },
  { key: "net", label: "Net income", kind: "total", values: ["3800.00", "2700.00"] },
];

export const ProfitAndLoss: Story = {
  args: {
    caption: "Profit and loss",
    columns: [
      { key: "p0", label: "Jan–Dec 2026" },
      { key: "p1", label: "Jan–Dec 2025" },
    ],
    rows,
    locale: "en-CA",
    labels,
    onDrill: () => undefined,
  },
};

export const TwelveComparisons: Story = {
  args: {
    caption: "Profit and loss by month",
    columns: Array.from({ length: 13 }, (_, i) => ({ key: `p${i}`, label: `Period ${i + 1}` })),
    rows: rows.map((row) => ({
      ...row,
      values: row.values.length ? Array.from({ length: 13 }, () => row.values[0] ?? null) : [],
    })),
    locale: "en-CA",
    labels,
    compact: true,
  },
};
