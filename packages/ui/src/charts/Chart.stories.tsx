import type { Meta, StoryObj } from "@storybook/react";

import { BarChart, LineChart, type ChartCategory, type ChartLabels } from "./Chart";

/**
 * Bar and line charts (K-05-T08): zero baseline, compact CAD axis, at most two series with a
 * legend, exact amounts in tooltips and in the "Show as table" fallback. An empty chart still
 * shows its axis from $0 (gap-60).
 */
const meta: Meta<typeof BarChart> = { title: "Charts/Bar and line", component: BarChart };
export default meta;
type Story = StoryObj<typeof BarChart>;

const months: ChartCategory[] = [
  { key: "2026-06", label: "Jun" },
  { key: "2026-07", label: "Jul" },
  { key: "2026-08", label: "Aug" },
  { key: "2026-09", label: "Sep" },
  { key: "2026-10", label: "Oct" },
  { key: "2026-11", label: "Nov" },
];

const labels: ChartLabels = {
  chart: "Cash in and out, last 6 months",
  showTable: "Show as table",
  showChart: "Show chart",
  category: "Month",
};

export const CashInAndOut: Story = {
  args: {
    categories: months,
    locale: "en-CA",
    labels,
    series: [
      {
        key: "in",
        label: "Money in",
        values: ["12400.00", "9800.50", "15250.00", "11020.00", "18400.00", "7300.00"],
      },
      {
        key: "out",
        label: "Money out",
        values: ["10100.00", "11250.00", "9900.00", "12000.75", "13480.00", "6900.00"],
      },
    ],
  },
};

export const EmptyShowsZeroAxis: Story = {
  args: {
    categories: months,
    locale: "en-CA",
    labels: { ...labels, chart: "Cash in and out, last 6 months: no activity" },
    series: [
      { key: "in", label: "Money in", values: [] },
      { key: "out", label: "Money out", values: [] },
    ],
  },
};

export const NetCashLine: Story = {
  render: () => (
    <LineChart
      categories={months}
      locale="fr-CA"
      labels={{
        ...labels,
        chart: "Encaisse nette",
        showTable: "Afficher le tableau",
        category: "Mois",
      }}
      series={[
        {
          key: "net",
          label: "Encaisse nette",
          values: ["2300", "-1449.5", "5350", "-980.75", "4920", "400"],
        },
      ]}
    />
  ),
};
