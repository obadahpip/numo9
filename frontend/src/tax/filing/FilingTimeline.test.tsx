import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import { blockState, daysIn, nextDay } from "./api";
import { FilingTimeline } from "./FilingTimeline";
import { CUSTOM, MONTHLY, MONTHS, Q1, Q2, Q3, QUARTERLY, QUARTERS } from "./fixtures";

/**
 * G-03a-T18 — the timeline matches the API's periods: one block per period in order, sized by
 * its days, coloured and named by state; switch markers; hover card with the due dates.
 */
it("draws one block per API period, in order, with its state and share of the days", async () => {
  const { container } = renderWithIntl(<FilingTimeline periods={QUARTERS} cycles={[QUARTERLY]} />);
  const timeline = screen.getByRole("region", { name: "Filing periods timeline" });
  const blocks = [...timeline.querySelectorAll<HTMLElement>("[data-period]")];
  expect(blocks.map((b) => b.dataset.period)).toEqual(QUARTERS.map((p) => p.start));
  expect(blocks.map((b) => b.dataset.state)).toEqual(["filed", "overdue", "due_soon", "open"]);
  const shares = blocks.map((b) => Number(b.dataset.share));
  expect(shares.reduce((a, b) => a + b, 0)).toBeCloseTo(1, 3); // no gap, no overlap
  expect(shares[0]).toBeCloseTo(90 / 365, 3);
  expect(
    within(timeline).getByRole("button", {
      name: "Period 2: 1 Apr 2026 – 30 Jun 2026, Overdue",
    }),
  ).toBeVisible();
  const legend = screen.getByRole("list", { name: "Legend" });
  for (const state of ["Filed", "Open", "Due soon", "Overdue"]) {
    expect(within(legend).getByText(state)).toBeVisible();
  }
  expect(within(legend).getByText(/next business day/)).toBeVisible();
  await expectNoAxeViolations(container);
});

it("marks where each frequency takes effect", () => {
  renderWithIntl(
    <FilingTimeline periods={[Q1, Q2, Q3, ...MONTHS]} cycles={[QUARTERLY, MONTHLY]} />,
  );
  const markers = [...document.querySelectorAll<HTMLElement>("[data-switch]")];
  expect(markers.map((m) => [m.dataset.switch, m.textContent])).toEqual([
    ["2026-01-01", "Quarterly from 1 Jan 2026"],
    ["2026-10-01", "Monthly from 1 Oct 2026"],
  ]);
  expect(markers[1]!.closest("[data-period]")).toHaveAttribute("data-period", "2026-10-01");
});

it("shows the hover card with due dates, an asterisk on a rolled one", async () => {
  renderWithIntl(<FilingTimeline periods={QUARTERS} cycles={[QUARTERLY]} />);
  await userEvent.tab();
  await userEvent.tab();
  await userEvent.tab();
  const card = await screen.findByRole("tooltip");
  expect(card).toHaveTextContent("Period 3");
  expect(card).toHaveTextContent("1 Jul 2026 – 30 Sep 2026");
  expect(card).toHaveTextContent("Return due 2 Nov 2026 *");
  expect(card).toHaveTextContent("Payment due 2 Nov 2026");
  expect(card).toHaveTextContent("Regular · Due soon");
});

it("offers to remove an unfiled out-of-cycle period only", async () => {
  const removed: string[] = [];
  renderWithIntl(
    <FilingTimeline
      periods={[Q1, Q2, Q3, CUSTOM]}
      cycles={[QUARTERLY]}
      onRemoveCustom={(p) => removed.push(p.id)}
    />,
  );
  const remove = screen.getByRole("button", {
    name: "Remove out-of-cycle period 1 Oct 2026 – 15 Nov 2026",
  });
  await userEvent.click(remove);
  expect(removed).toEqual([CUSTOM.id]);
  expect(screen.getAllByRole("button", { name: /^Remove/ })).toHaveLength(1);
});

it("helpers: block state, days and next day", () => {
  expect(blockState({ ...Q2, status: "paid" })).toBe("filed");
  expect(blockState(Q2)).toBe("overdue");
  expect(daysIn("2028-02-01", "2028-02-29")).toBe(29);
  expect(nextDay("2026-12-31")).toBe("2027-01-01");
});
