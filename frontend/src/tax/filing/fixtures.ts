/** Fixtures of the filing UI tests (G-03a-T18…T21): a quarterly registration in 2026. */
import type { FilingCycle, FilingDiff, FilingPeriod, PeriodsResponse } from "./api";

export const ORG = "acme";
export const REG = "11111111-2222-4333-8444-555555555555";
export const BASE = `/api/v1/o/${ORG}/tax/registrations/${REG}`;

export function period(over: Partial<FilingPeriod> & Pick<FilingPeriod, "start" | "end">) {
  return {
    id: `p-${over.start}`,
    kind: "regular",
    frequency: "quarterly",
    sequence_no: 1,
    due_date: "2026-04-30",
    payment_due_date: "2026-04-30",
    status: "open",
    note: "",
    attention: "",
    due_rolled: false,
    instalments: [],
    ...over,
  } satisfies FilingPeriod as FilingPeriod;
}

export const Q1 = period({ start: "2026-01-01", end: "2026-03-31", status: "filed" });
export const Q2 = period({
  start: "2026-04-01",
  end: "2026-06-30",
  sequence_no: 2,
  status: "closed",
  attention: "overdue",
  due_date: "2026-07-31",
  payment_due_date: "2026-07-31",
});
export const Q3 = period({
  start: "2026-07-01",
  end: "2026-09-30",
  sequence_no: 3,
  status: "closed",
  attention: "due_soon",
  due_date: "2026-11-02",
  payment_due_date: "2026-11-02",
  due_rolled: true,
});
export const Q4 = period({
  start: "2026-10-01",
  end: "2026-12-31",
  sequence_no: 4,
  due_date: "2027-02-01",
  payment_due_date: "2027-02-01",
  due_rolled: true,
});
export const QUARTERS = [Q1, Q2, Q3, Q4];

export const QUARTERLY: FilingCycle = {
  id: "c-1",
  frequency: "quarterly",
  effective_from: "2026-01-01",
  approval_ref: "",
  approval_date: null,
  note: "",
  created_by: "Dana Lee",
  created_at: "2026-01-05T15:00:00Z",
};
export const MONTHLY: FilingCycle = {
  id: "c-2",
  frequency: "monthly",
  effective_from: "2026-10-01",
  approval_ref: "2026-GST-48812",
  approval_date: "2026-09-10",
  note: "CRA letter",
  created_by: "Sam Patel",
  created_at: "2026-09-12T14:30:00Z",
};

export const MONTHS = ["10", "11", "12"].map((month, index) =>
  period({
    start: `2026-${month}-01`,
    end: `2026-${month}-${month === "11" ? "30" : "31"}`,
    frequency: "monthly",
    sequence_no: 4 + index,
  }),
);

export function periodsResponse(results: FilingPeriod[] = QUARTERS): PeriodsResponse {
  return {
    registration: {
      id: REG,
      type: "rt",
      number: "12345 6782 RT0001",
      start_date: "2026-01-01",
      stop_date: "2026-12-31",
    },
    today: "2026-10-20",
    results,
  };
}

/** Quarterly → monthly from 1 Oct: Q4 removed, three months added. */
export const SWITCH_DIFF: FilingDiff = {
  removed: [Q4],
  added: MONTHS,
  changed: [],
  periods: [Q1, Q2, Q3, ...MONTHS],
  warnings: [
    {
      code: "tax.filing.not_fiscal_year_start",
      message:
        "2026-10-01 isn't the start of your financial year. The switch is saved with approval 2026-GST-48812.",
    },
  ],
};

export const CUSTOM = period({
  start: "2026-10-01",
  end: "2026-11-15",
  kind: "custom",
  sequence_no: 4,
});
export const AFTER_CUSTOM = period({
  start: "2026-11-16",
  end: "2026-12-31",
  kind: "stub",
  sequence_no: 5,
});
/** 1 Oct–15 Nov out of cycle: Q4 removed, the custom period and a realigned stub added. */
export const CUSTOM_DIFF: FilingDiff = {
  removed: [Q4],
  added: [CUSTOM, AFTER_CUSTOM],
  changed: [],
  periods: [Q1, Q2, Q3, CUSTOM, AFTER_CUSTOM],
  warnings: [],
};
