import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { StaffActivity } from "./StaffActivity";

/** V-05-T08 — the staff member's heatmap from the activity API, with its table toggle. */

afterEach(() => vi.unstubAllGlobals());

it("shows the audit-log counts as a heatmap and as a table", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            from: "2025-11-19",
            to: "2026-11-18",
            total: 5,
            days: [
              { date: "2026-11-02", count: 3 },
              { date: "2026-11-05", count: 2 },
            ],
          }),
          { headers: { "Content-Type": "application/json" } },
        ),
    ),
  );
  const { container } = renderWithIntl(<StaffActivity practice="p" user="u" />);
  const chart = await screen.findByRole("img", {
    name: "Activity, last 12 months: 5 changes in the audit log",
  });
  expect(chart.querySelector('rect[data-date="2026-11-02"] title')?.textContent).toBe(
    "3 changes on 2 Nov 2026",
  );
  expect(chart.querySelector('rect[data-date="2026-11-03"] title')?.textContent).toBe(
    "No changes on 3 Nov 2026",
  );
  await expectNoAxeViolations(container);
  await userEvent.click(screen.getByRole("button", { name: "Show as a table" }));
  expect(screen.getByRole("table")).toHaveTextContent("2 Nov 2026");
  await expectNoAxeViolations(container);
});

it("renders nothing without access", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ code: "permission.denied" }), { status: 403 })),
  );
  const { container } = renderWithIntl(<StaffActivity practice="p" user="u" />);
  await new Promise((resolve) => setTimeout(resolve, 20));
  expect(container).toBeEmptyDOMElement();
});
