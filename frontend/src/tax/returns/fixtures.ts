/** Test data for the return worksheet (G-03-T11, T12). */
import type { ReturnLine, TaxReturn } from "./api";

const LABELS: [string, string][] = [
  ["101", "Sales and other revenue"],
  ["103", "GST/HST collected or collectible"],
  ["104", "Adjustments to be added to the net tax"],
  ["105", "Total GST/HST and adjustments for period"],
  ["106", "Input tax credits (ITCs) for the current period"],
  ["107", "Adjustments to be deducted"],
  ["108", "Total ITCs and adjustments"],
  ["109", "Net tax"],
  ["110", "Instalments and other annual filer payments"],
  ["111", "Rebates"],
  ["112", "Total other credits"],
  ["113A", "Balance (line 109 minus line 112)"],
  ["113B", "Other debits"],
  ["113C", "Balance (line 113 A plus line 113 B)"],
  ["114", "Refund claimed"],
  ["115", "Payment enclosed"],
];

const AMOUNTS: Record<string, string> = {
  "101": "1200.00",
  "103": "130.00",
  "105": "130.00",
  "106": "63.50",
  "108": "63.50",
  "109": "66.50",
  "113A": "66.50",
  "113C": "66.50",
  "115": "66.50",
};

const DRILL = new Set(["101", "103", "104", "106", "107"]);
const ENTRY = new Set(["104", "107", "110", "111", "113B"]);

export const LINES: ReturnLine[] = LABELS.map(([line, label]) => ({
  line,
  label,
  amount: AMOUNTS[line] ?? "0.00",
  drill: DRILL.has(line),
  entry: ENTRY.has(line),
}));

export const RETURN_ID = "7d2b0a52-41c7-4c3e-9a55-0f6f3c7a0001";

export function taxReturn(over: Partial<TaxReturn> = {}): TaxReturn {
  return {
    id: RETURN_ID,
    registration: "reg-1",
    period: {
      id: "per-1",
      start: "2026-06-01",
      end: "2026-06-30",
      label: "2026-06-01 – 2026-06-30",
      status: "open",
      due_date: "2026-07-31",
      locked: false,
    },
    version: 1,
    status: "draft",
    method: "regular",
    is_current: true,
    lines: LINES,
    entries: {},
    prepared_by: { id: "u1", name: "Dana Lee" },
    prepared_at: "2026-07-02T10:00:00Z",
    reviewed_by: null,
    filed_by: null,
    filed_on: null,
    confirmation_no: "",
    amend_reason: "",
    versions: [
      {
        id: RETURN_ID,
        version: 1,
        status: "draft",
        current: true,
        filed_on: null,
        confirmation_no: "",
        amend_reason: "",
      },
    ],
    changed: [],
    ...over,
  };
}
