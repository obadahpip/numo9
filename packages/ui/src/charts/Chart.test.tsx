import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import {
  BarChart,
  barPath,
  CHART_SERIES,
  chartTicks,
  formatAxisMoney,
  LineChart,
  type ChartCategory,
  type ChartLabels,
} from "./Chart";

/**
 * K-05-T08 — chart components: zero rendering rule (an empty chart's axis shows 0, never "—k"),
 * CAD axis format, table fallback with the exact amounts, at most two series with a legend.
 */
const months: ChartCategory[] = [
  { key: "06", label: "Jun" },
  { key: "07", label: "Jul" },
  { key: "08", label: "Aug" },
];
const labels: ChartLabels = {
  chart: "Cash in and out",
  showTable: "Show as table",
  showChart: "Show chart",
  category: "Month",
};

const axisLabels = (container: HTMLElement) =>
  [...container.querySelectorAll("[data-tick] text")].map((t) => t.textContent);

describe("chart scale (K-05-T08)", () => {
  it("always includes zero and uses nice steps", () => {
    expect(chartTicks([1200, 18400, 9800])).toEqual([0, 5000, 10000, 15000, 20000]);
    expect(chartTicks([-1449.5, 5350])).toEqual([-2000, 0, 2000, 4000, 6000]);
    expect(chartTicks([-300, -100])).toEqual([-300, -200, -100, 0]);
  });

  it("an empty or all-zero series still has a real axis", () => {
    expect(chartTicks([])).toEqual([0, 1]);
    expect(chartTicks([0, 0, 0])).toEqual([0, 1]);
  });

  it("formats the axis in compact Canadian dollars", () => {
    expect([0, 1, 5000, 12500, 1_200_000, -2500].map((v) => formatAxisMoney(v, "en-CA"))).toEqual([
      "$0",
      "$1",
      "$5K",
      "$12.5K",
      "$1.2M",
      "-$2.5K",
    ]);
    expect(formatAxisMoney(5000, "fr-CA").replace(/\s/g, " ")).toBe("5 k $");
    expect(formatAxisMoney(-0, "en-CA")).toBe("$0");
  });

  it("rounds bars only at their data end", () => {
    expect(barPath(10, 20, 100, 40)).toBe("M10,100V44Q10,40 14,40H26Q30,40 30,44V100Z");
    expect(barPath(10, 20, 100, 160)).toBe("M10,100V156Q10,160 14,160H26Q30,160 30,156V100Z");
    expect(barPath(10, 20, 100, 100)).toBe(""); // a zero bar draws nothing above the zero line
  });
});

describe("BarChart (K-05-T08)", () => {
  it("an empty chart shows $0 on its axis, never a dash or a bare 'k'", () => {
    const { container } = render(
      <BarChart
        categories={months}
        locale="en-CA"
        labels={labels}
        series={[{ key: "in", label: "Money in", values: [] }]}
      />,
    );
    expect(axisLabels(container)).toEqual(["$0", "$1"]);
    expect(container.textContent).not.toMatch(/—|–k|-k|\bk\b/);
    expect(container.querySelectorAll("path")).toHaveLength(0);
    expect(screen.getByRole("img", { name: "Cash in and out" })).toBeInTheDocument();
  });

  it("draws two series with the fixed colours, a legend and exact tooltips", () => {
    const { container } = render(
      <BarChart
        categories={months}
        locale="en-CA"
        labels={labels}
        series={[
          { key: "in", label: "Money in", values: ["1250.00", "0", "900.5"] },
          { key: "out", label: "Money out", values: ["400", "300", "0"] },
        ]}
      />,
    );
    expect(container.querySelector("[data-series=in]")).toHaveAttribute("fill", CHART_SERIES[0]);
    expect(container.querySelector("[data-series=out]")).toHaveAttribute("fill", CHART_SERIES[1]);
    const legend = container.querySelector("[data-chart-legend]") as HTMLElement;
    expect(
      within(legend)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual(["Money in", "Money out"]);
    const bar = container.querySelector("[data-bar='in:06'] title");
    expect(bar).toHaveTextContent("Money in, Jun: $1,250.00");
    expect(container.querySelector("[data-bar='in:07'] path")).toBeNull(); // zero: no bar
    expect(axisLabels(container)).toEqual(["$0", "$500", "$1K", "$1.5K"]);
  });

  it("needs no legend for one series", () => {
    const { container } = render(
      <BarChart
        categories={months}
        locale="en-CA"
        labels={labels}
        series={[{ key: "in", label: "Money in", values: ["1", "2", "3"] }]}
      />,
    );
    expect(container.querySelector("[data-chart-legend]")).toBeNull();
  });

  it("never cycles colours: a third series is left out with a warning", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const { container } = render(
      <BarChart
        categories={months}
        locale="en-CA"
        labels={labels}
        series={["a", "b", "c"].map((key) => ({ key, label: key, values: ["1", "2", "3"] }))}
      />,
    );
    expect(warn).toHaveBeenCalled();
    expect(container.querySelectorAll("[data-series]")).toHaveLength(2);
    warn.mockRestore();
  });

  it("switches to a table of the exact amounts and back", async () => {
    render(
      <BarChart
        categories={months}
        locale="fr-CA"
        labels={labels}
        series={[{ key: "in", label: "Money in", values: ["1250.00"] }]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Show as table" }));
    const table = screen.getByRole("table", { name: "Cash in and out" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((r) => r.textContent?.replace(/\s/g, " "))).toEqual([
      "Jun1 250,00 $",
      "Jul0,00 $",
      "Aug0,00 $",
    ]);
    expect(screen.queryByRole("img")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Show chart" }));
    expect(screen.getByRole("img", { name: "Cash in and out" })).toBeInTheDocument();
  });

  it("has no axe violations", async () => {
    render(
      <BarChart
        categories={months}
        locale="en-CA"
        labels={labels}
        series={[{ key: "in", label: "Money in", values: ["1", "2", "3"] }]}
      />,
    );
    await expectNoAxeViolations();
  });
});

describe("LineChart (K-05-T08)", () => {
  it("draws a 2 px line with 8 px markers, below zero when negative", () => {
    const { container } = render(
      <LineChart
        categories={months}
        locale="en-CA"
        labels={labels}
        series={[{ key: "net", label: "Net cash", values: ["2300", "-1449.5", "0"] }]}
      />,
    );
    const line = container.querySelector("polyline") as SVGPolylineElement;
    expect(line).toHaveAttribute("stroke-width", "2");
    const points = container.querySelectorAll("circle");
    expect(points).toHaveLength(3);
    expect(points[0]).toHaveAttribute("r", "4");
    const zeroY = Number(
      container.querySelector("[data-tick='0'] line")?.getAttribute("y1") ?? "NaN",
    );
    expect(Number(points[1]?.getAttribute("cy"))).toBeGreaterThan(zeroY);
    expect(Number(points[2]?.getAttribute("cy"))).toBe(zeroY);
    expect(points[1]?.querySelector("title")).toHaveTextContent("Net cash, Jul: -$1,449.50");
  });

  it("an empty line chart shows $0, never '—k'", () => {
    const { container } = render(
      <LineChart
        categories={months}
        locale="en-CA"
        labels={labels}
        series={[{ key: "net", label: "Net cash", values: [] }]}
      />,
    );
    expect(axisLabels(container)).toEqual(["$0", "$1"]);
  });
});
