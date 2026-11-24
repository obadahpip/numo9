/** Report fixtures shared by the Vitest suites (K-01-T12…T16). */
import type { Catalogue, ReportBody, ReportRowData, ReportSummary } from "./api";

export { serveJson } from "@/banking/fixtures";

export const ORG = "acme";

export const summary = (over: Partial<ReportSummary>): ReportSummary => ({
  id: "trial_balance",
  slug: "trial-balance",
  name: "Trial balance",
  description: "Every account's debit or credit balance on a date, in one book.",
  category: "financial",
  feature: "accounting.reports.read",
  product: "accounting",
  product_name: "Accounting",
  params: [
    { name: "as_of", kind: "date", default: null, choices: [], required: false },
    {
      name: "book",
      kind: "choice",
      default: "accounting",
      choices: ["accounting", "tax"],
      required: false,
    },
  ],
  available: true,
  favourite: false,
  ...over,
});

export const PERIOD_PARAMS: ReportSummary["params"] = [
  { name: "date_from", kind: "date", default: null, choices: [], required: true },
  { name: "date_to", kind: "date", default: null, choices: [], required: true },
  {
    name: "book",
    kind: "choice",
    default: "accounting",
    choices: ["accounting", "tax"],
    required: false,
  },
];

export const CATALOGUE: Catalogue = {
  categories: [
    {
      key: "financial",
      reports: [
        summary({}),
        summary({
          id: "account_activity",
          slug: "account-activity",
          name: "Account activity",
          description: "Debits, credits and net movement of each account for a period.",
          params: PERIOD_PARAMS,
        }),
      ],
    },
    {
      key: "tax",
      reports: [
        summary({
          id: "gst_hst_summary",
          slug: "gst-hst-summary",
          name: "GST/HST summary",
          description: "Collected and paid GST/HST by tax code for a period.",
          category: "tax",
          feature: "tax.reports.read",
          product: "tax",
          product_name: "Tax",
          available: false,
          params: PERIOD_PARAMS,
        }),
      ],
    },
  ],
  favourites: [],
  drafts: [],
  published: [],
  custom: [],
};

export const row = (over: Partial<ReportRowData>): ReportRowData => ({
  key: "account:1000",
  label: "1000 · Chequing",
  kind: "row",
  level: 0,
  values: ["3650.00"],
  drill: { account: "1000", book: "accounting", from: "2026-05-01", to: "2026-07-31" },
  notes: {},
  ...over,
});

export const BODY: ReportBody = {
  report: "account_activity",
  params: { date_from: "2026-05-01", date_to: "2026-07-31", book: "accounting" },
  columns: [{ key: "net", label: "Net movement" }],
  rows: [
    row({}),
    row({
      key: "account:4000",
      label: "4000 · Sales",
      values: ["-6200.00"],
      drill: { account: "4000", book: "accounting", from: "2026-05-01", to: "2026-07-31" },
    }),
    row({
      key: "account:5400",
      label: "5400 · Rent",
      values: ["2400.00"],
      drill: { account: "5400", book: "accounting", from: "2026-05-01", to: "2026-07-31" },
    }),
  ],
  totals: [row({ key: "total", label: "Total", kind: "total", values: ["-150.00"], drill: null })],
  header: {
    title: "Account activity",
    display_name: "Refined Interiors",
    legal_name: "Refined Interiors Inc.",
    period_label: "1 May 2026 to 31 Jul 2026",
    status_label: "",
    basis_label: "Basis: Accrual (organisation default)",
    book_label: "Accounting book",
  },
  notes: "",
  unplaced_notes: [],
};
