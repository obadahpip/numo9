import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import { blankLine } from "./ExpenseClaimForm";
import type { FormLine } from "./fields";
import { MileageLine, clearRates } from "./MileageLine";

/**
 * E-04-T10 — the mileage line shows the amount live at the CRA rate of its date, with both tiers
 * when the trip crosses 5,000 km (year to date from the server).
 */
function serve(yearToDate: string) {
  clearRates();
  const fetcher = vi.fn(
    serveJson((url) =>
      url.includes("/mileage-rate")
        ? {
            body: {
              date: "2026-06-15",
              region: "provinces",
              first_tier_rate: "0.73",
              second_tier_rate: "0.67",
              tier_threshold_km: 5000,
              year_to_date_km: yearToDate,
            },
          }
        : { status: 404, body: {} },
    ),
  );
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}

function Harness() {
  const [line, setLine] = useState<FormLine>({ ...blankLine("mileage"), date: "2026-06-15" });
  return (
    <MileageLine
      org="acme"
      line={line}
      index={0}
      lines={[line]}
      onChange={(patch) => setLine((now) => ({ ...now, ...patch }))}
      onRemove={() => undefined}
    />
  );
}

test("the amount is shown live as the kilometres are typed", async () => {
  const fetcher = serve("0");
  renderWithIntl(<Harness />);
  await waitFor(() => expect(fetcher).toHaveBeenCalled());
  await userEvent.type(screen.getByLabelText("Distance (km)"), "100");
  expect(await screen.findByText("$73.00")).toBeVisible();
  expect(screen.getByText("100.0 km × $0.73 = $73.00")).toBeVisible();
  await userEvent.type(screen.getByLabelText("Distance (km)"), ".5");
  expect(await screen.findByText("$73.36")).toBeVisible(); // 100.5 × 0.73 = 73.365 → 73.36
  const asked = fetcher.mock.calls.map((call) => String(call[0]));
  expect(asked).toEqual(["/api/v1/o/acme/expense-claims/mileage-rate?date=2026-06-15"]); // once
});

test("a trip crossing 5,000 km shows both tiers", async () => {
  serve("4900");
  renderWithIntl(<Harness />);
  await userEvent.type(screen.getByLabelText("Distance (km)"), "300");
  expect(await screen.findByText("$207.00")).toBeVisible();
  expect(screen.getByText("100.0 km × $0.73 = $73.00")).toBeVisible();
  expect(screen.getByText("200.0 km × $0.67 = $134.00")).toBeVisible();
});
