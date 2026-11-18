import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { expectNoAxeViolations } from "../test/axe";
import { ActivityHeatmap, heatmapStep, type ActivityHeatmapLabels } from "./ActivityHeatmap";

/**
 * V-05-T08 — heatmap component: SVG squares on a colour scale, the number in each tooltip, a
 * table fallback; axe passes in both views.
 */

const labels: ActivityHeatmapLabels = {
  chart: "Activity, last 4 weeks: 9 changes",
  less: "Less",
  more: "More",
  showTable: "Show as a table",
  showChart: "Show as a chart",
  tableDate: "Day",
  tableCount: "Changes",
  day: (count, date) => `${count} changes on ${date}`,
  date: (date) => date,
  empty: "No activity in this period.",
};
const DAYS = [
  { date: "2026-11-02", count: 6 },
  { date: "2026-11-03", count: 1 },
  { date: "2026-11-05", count: 2 },
];

it("scales colours to the busiest day", () => {
  expect([0, 1, 2, 3, 6].map((n) => heatmapStep(n, 6))).toEqual([0, 1, 2, 2, 4]);
  expect(heatmapStep(5, 0)).toBe(0);
});

it("draws one square per day with its number, and toggles to a table", async () => {
  const { container } = render(
    <ActivityHeatmap days={DAYS} from="2026-10-22" to="2026-11-18" labels={labels} />,
  );
  const chart = screen.getByRole("img", { name: "Activity, last 4 weeks: 9 changes" });
  const squares = chart.querySelectorAll("rect");
  expect(squares).toHaveLength(28);
  const busiest = chart.querySelector('rect[data-date="2026-11-02"]');
  expect(busiest?.getAttribute("data-count")).toBe("6");
  expect(busiest?.querySelector("title")?.textContent).toBe("6 changes on 2026-11-02");
  expect(chart.querySelector('rect[data-date="2026-11-04"] title')?.textContent).toBe(
    "0 changes on 2026-11-04",
  );
  expect(busiest?.getAttribute("fill")).not.toBe(
    chart.querySelector('rect[data-date="2026-11-03"]')?.getAttribute("fill"),
  );
  await expectNoAxeViolations(container);

  await userEvent.click(screen.getByRole("button", { name: "Show as a table" }));
  const table = screen.getByRole("table");
  const rows = within(table).getAllByRole("row").slice(1);
  expect(rows.map((row) => row.textContent)).toEqual(["2026-11-026", "2026-11-031", "2026-11-052"]);
  expect(screen.getByRole("button", { name: "Show as a chart" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expectNoAxeViolations(container);
});

it("starts weeks on Monday when asked", () => {
  render(
    <ActivityHeatmap days={[]} from="2026-11-02" to="2026-11-08" labels={labels} weekStart={1} />,
  );
  const first = screen.getByRole("img").querySelector('rect[data-date="2026-11-02"]');
  expect(first?.getAttribute("y")).toBe("0"); // 2 Nov 2026 is a Monday: the first row
});

it("shows the empty table", async () => {
  render(<ActivityHeatmap days={[]} from="2026-11-01" to="2026-11-07" labels={labels} />);
  await userEvent.click(screen.getByRole("button", { name: "Show as a table" }));
  expect(screen.getByText("No activity in this period.")).toBeVisible();
});
