/** Report API answers for the K-01 Playwright suites (shapes of backend/numo9/reports/api.py). */
const PERIOD = [
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

const report = (over: Record<string, unknown>) => ({
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

export const CATALOGUE = {
  categories: [
    {
      key: "financial",
      reports: [
        report({}),
        report({
          id: "account_activity",
          slug: "account-activity",
          name: "Account activity",
          description: "Debits, credits and net movement of each account for a period.",
          params: PERIOD,
        }),
        report({
          id: "profit_and_loss",
          slug: "profit-and-loss",
          name: "Profit and loss",
          description: "Income, expenses and net income for a period, with comparisons.",
          params: [
            ...PERIOD,
            {
              name: "compare",
              kind: "choice",
              default: "none",
              choices: ["none", "previous", "prior_year"],
              required: false,
            },
            { name: "periods", kind: "int", default: 1, choices: [], required: false },
            {
              name: "basis",
              kind: "choice",
              default: "",
              choices: ["", "accrual", "cash"],
              required: false,
            },
            { name: "tracking", kind: "text", default: "", choices: [], required: false },
          ],
        }),
        report({
          id: "balance_sheet",
          slug: "balance-sheet",
          name: "Balance sheet",
          description: "Assets, liabilities and equity on a date.",
        }),
      ],
    },
    {
      key: "tax",
      reports: [
        report({
          id: "gst_hst_summary",
          slug: "gst-hst-summary",
          name: "GST/HST summary",
          description: "Collected and paid GST/HST by tax code for a period.",
          category: "tax",
          feature: "tax.reports.read",
          product: "tax",
          product_name: "Tax",
          available: false,
          params: PERIOD,
        }),
      ],
    },
  ],
  favourites: [],
  drafts: [],
  published: [],
  custom: [],
};

const header = (title: string, period = "1 Jan 2026 to 31 Dec 2026") => ({
  title,
  display_name: "Refined Interiors",
  legal_name: "Refined Interiors Inc.",
  period_label: period,
  status_label: "",
  basis_label: "Basis: Accrual (organisation default)",
  book_label: "Accounting book",
});

const drill = (account: string) => ({
  account,
  book: "accounting",
  from: "2026-01-01",
  to: "2026-12-31",
});

/** A P&L with `columns` value columns (1 + comparisons). */
export function profitAndLoss(columns = 1) {
  const cols = Array.from({ length: columns }, (_, i) => ({
    key: `p${i}`,
    label: i === 0 ? "Jan–Dec 2026" : `Comparison ${i}`,
  }));
  const values = (amount: string) => cols.map(() => amount);
  return {
    report: "profit_and_loss",
    params: {
      date_from: "2026-01-01",
      date_to: "2026-12-31",
      book: "accounting",
      compare: "none",
      periods: 1,
    },
    columns: cols,
    rows: [
      {
        key: "section:income",
        label: "Income",
        kind: "section",
        level: 0,
        values: [],
        drill: null,
        notes: {},
      },
      {
        key: "account:4000",
        label: "4000 · Sales",
        kind: "row",
        level: 1,
        values: values("6200.00"),
        drill: drill("4000"),
        notes: {},
      },
      {
        key: "section:expenses",
        label: "Expenses",
        kind: "section",
        level: 0,
        values: [],
        drill: null,
        notes: {},
      },
      {
        key: "account:5400",
        label: "5400 · Rent",
        kind: "row",
        level: 1,
        values: values("2400.00"),
        drill: drill("5400"),
        notes: {},
      },
    ],
    totals: [
      {
        key: "net_income",
        label: "Net income",
        kind: "total",
        level: 0,
        values: values("3800.00"),
        drill: null,
        notes: {},
      },
    ],
    header: header("Profit and loss"),
    notes: "",
    unplaced_notes: [],
  };
}

export const EMPTY_PNL = {
  ...profitAndLoss(1),
  rows: [],
  totals: [
    {
      key: "net_income",
      label: "Net income",
      kind: "total",
      level: 0,
      values: [null],
      drill: null,
      notes: {},
    },
  ],
};

export const SALES_LINES = {
  account: { id: "a4000", code: "4000", name: "Sales" },
  total: "-6200.00",
  count: 1,
  page: 1,
  pages: 1,
  page_size: 50,
  lines: [
    {
      date: "2026-05-03",
      journal: "INV-0001",
      narration: "Invoice INV-0001",
      description: "Design consultation",
      contact: "Maple & Pine",
      debit: "0.00",
      credit: "6200.00",
      amount: "-6200.00",
      status: "posted",
      source: {
        type: "sales.invoice",
        url: "/o/acme/sales/invoices/7f2c9a40-3b1e-4c8a-9d6f-1a2b3c4d5e6f",
        journal_url: "/o/acme/accounting/journals/1b2c3d4e-5f60-4718-8a9b-0c1d2e3f4a5b",
      },
    },
  ],
};

/** K-02: a balance sheet with Petty Cash overdrawn and reclassified (K-02-T04). */
export function balanceSheet(asOf: string) {
  const row = (key: string, label: string, kind: string, level: number, values: string[]) => ({
    key,
    label,
    kind,
    level,
    values,
    drill: kind === "row" ? drill(key.split(":")[1] ?? "") : null,
    notes: {},
  });
  return {
    report: "balance_sheet",
    params: { as_of: asOf, compare: "none", periods: 1, book: "accounting" },
    columns: [{ key: "b0", label: asOf }],
    rows: [
      row("section:assets", "Assets", "section", 0, []),
      row("group:current_assets", "Current assets", "section", 1, []),
      row("account:1000", "1000 · Chequing", "row", 2, ["5000.00"]),
      row("account:1050", "1050 · Old float", "row", 2, ["0.00"]),
      row("total:current_assets", "Total current assets", "total", 1, ["5000.00"]),
      row("total:assets", "Total assets", "total", 0, ["5000.00"]),
      row("section:liabilities", "Liabilities", "section", 0, []),
      row("group:current_liabilities", "Current liabilities", "section", 1, []),
      row("overdraft:1010", "Bank overdraft — Petty Cash", "row", 2, ["994.17"]),
      row("total:current_liabilities", "Total current liabilities", "total", 1, ["994.17"]),
      row(
        "note:overdraft",
        "Overdrawn bank and cash accounts are presented as current liabilities (ASPE 1510).",
        "text",
        1,
        [],
      ),
      row("total:liabilities", "Total liabilities", "total", 0, ["994.17"]),
      row("section:equity", "Equity", "section", 0, []),
      row("current_year_earnings", "Current year earnings", "row", 1, ["4005.83"]),
      row("total:equity", "Total equity", "total", 0, ["4005.83"]),
    ],
    totals: [
      row("total:liabilities_and_equity", "Total liabilities and equity", "total", 0, ["5000.00"]),
    ],
    header: header("Balance sheet"),
    notes: "",
    unplaced_notes: [],
  };
}
