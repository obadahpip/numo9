import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import { ActivityHeatmap } from "./Heatmap";

/**
 * K-09-T24 — Activity tab: the calendar grid shows the audit counts per day (organisation time
 * zone), the table alternative lists the same numbers, the people list shows the dormant owner,
 * and the person filter asks the API for that person.
 */
const HEATMAP = {
  from: "2025-11-27",
  to: "2026-11-26",
  time_zone: "America/Toronto",
  total: 16,
  days: [
    { date: "2026-06-15", count: 12 },
    { date: "2026-07-26", count: 4 },
  ],
  people: [
    { id: "u-tarik", name: "Tarik Dugmag", count: 12, last: "2026-06-15T10:00:00-04:00" },
    { id: "u-dana", name: "Dana Lee", count: 4, last: "2026-07-26T10:00:00-04:00" },
  ],
};

afterEach(() => vi.unstubAllGlobals());

describe("ActivityHeatmap", () => {
  it("shows the audit counts as a grid, a table and per person", async () => {
    const fetcher = vi.fn(async (url: string | URL | Request) => {
      const body = String(url).includes("user=u-dana")
        ? { ...HEATMAP, total: 4, days: [HEATMAP.days[1]], people: [HEATMAP.people[1]] }
        : HEATMAP;
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetcher);
    const { container } = renderWithIntl(<ActivityHeatmap org="refined" locale="en-CA" />);
    const grid = await screen.findByRole("img", { name: /16 actions from/ });
    const busy = grid.querySelector('[data-day="2026-06-15"]');
    expect(busy).toHaveAttribute("data-count", "12");
    expect(busy).toHaveAttribute("data-level", "4");
    expect(busy).toHaveAttribute("title", expect.stringContaining("12 actions"));
    const counted = [...grid.querySelectorAll("[data-count]")].reduce(
      (n, cell) => n + Number(cell.getAttribute("data-count")),
      0,
    );
    expect(counted).toBe(HEATMAP.total); // = the audit log
    expect(grid.querySelectorAll("[data-day]")).toHaveLength(365);

    await userEvent.click(screen.getByRole("button", { name: "Show as table" }));
    const table = container.querySelector("[data-heatmap-table]") as HTMLElement;
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(table).getByText("12")).toBeInTheDocument();
    const people = container.querySelector("[data-heatmap-people]") as HTMLElement;
    expect(within(people).getByText("Dana Lee")).toBeInTheDocument();
    await expectNoAxeViolations(container);

    await userEvent.selectOptions(screen.getByLabelText("Person"), "u-dana");
    await waitFor(() => expect(String(fetcher.mock.calls.at(-1)?.[0])).toContain("user=u-dana"));
    await screen.findByRole("img", { name: /4 actions from/ });
  });
});
