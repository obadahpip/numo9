import type { Meta, StoryObj } from "@storybook/react";

import { ActivityHeatmap, type ActivityHeatmapLabels } from "./ActivityHeatmap";

/**
 * Activity heatmap (V-05-T08): a staff member's daily changes for 12 months — colour scale plus
 * the number in every square's tooltip and a table alternative (the a11y addon checks both).
 */
const meta: Meta<typeof ActivityHeatmap> = {
  title: "Charts/ActivityHeatmap",
  component: ActivityHeatmap,
};
export default meta;
type Story = StoryObj<typeof ActivityHeatmap>;

const labels: ActivityHeatmapLabels = {
  chart: "Activity, last 12 months",
  less: "Less",
  more: "More",
  showTable: "Show as a table",
  showChart: "Show as a chart",
  tableDate: "Day",
  tableCount: "Changes",
  day: (count, date) => `${count} ${count === 1 ? "change" : "changes"} on ${date}`,
  date: (date) => date,
  empty: "No activity in this period.",
};

function sample(): { date: string; count: number }[] {
  const out: { date: string; count: number }[] = [];
  const start = Date.UTC(2025, 10, 19);
  for (let i = 0; i < 365; i += 1) {
    const day = new Date(start + i * 86_400_000);
    const weekday = day.getUTCDay();
    const count = weekday === 0 || weekday === 6 ? 0 : (i * 7) % 23;
    if (count) out.push({ date: day.toISOString().slice(0, 10), count });
  }
  return out;
}

export const TwelveMonths: Story = {
  args: { days: sample(), from: "2025-11-19", to: "2026-11-18", labels },
};

export const NoActivity: Story = {
  args: { days: [], from: "2025-11-19", to: "2026-11-18", labels },
};
