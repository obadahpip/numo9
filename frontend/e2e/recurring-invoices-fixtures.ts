import type { Page } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";
import { CUSTOMER, ORG, REVENUE } from "./invoices-fixtures";

/** Mocks of the recurring invoice suites (D-04-T08…T10): the API shapes of recurring_api.py. */
export { CUSTOMER, ORG, REVENUE };
export const TEMPLATE = "2c2c2c2c-0000-4000-8000-000000000001";
export const INVOICE = "1a1a1a1a-0000-4000-8000-000000000001";
export const DATES = [
  "2026-07-15",
  "2026-08-15",
  "2026-09-15",
  "2026-10-15",
  "2026-11-15",
  "2026-12-15",
];

const account = {
  id: REVENUE,
  code: "4000",
  name: "Sales",
  type: "revenue",
  subtype: "revenue",
  subtype_label: "",
  system_role: "",
  is_bank: false,
  depth: 1,
  has_children: false,
  require_contact: false,
  require_tracking: false,
  require_attachment: false,
  default_tax_key: "",
};

export function row(over: Record<string, unknown> = {}) {
  return {
    id: TEMPLATE,
    name: "Monthly bookkeeping",
    status: "active",
    customer: { id: CUSTOMER, name: "Maple Leaf Supply Ltd." },
    reference: "Bookkeeping {{month}} {{year}}",
    mode: "draft",
    rrule: "FREQ=MONTHLY;INTERVAL=1",
    start_date: "2026-06-15",
    end_date: null,
    next_run: "2026-07-15",
    last_run: "2026-06-15",
    paused: false,
    generated: 1,
    skipped: 1,
    url: `/o/${ORG}/sales/recurring-invoices/${TEMPLATE}`,
    ...over,
  };
}

const line = {
  position: 0,
  item: null,
  description: "Bookkeeping — {{month}}",
  quantity: "1.0000",
  unit_price: "300.0000",
  discount_type: "none",
  discount_value: "0.0000",
  account: { id: REVENUE, code: "4000", name: "Sales" },
  tax_code: null,
  tax_overridden: false,
  tracking: {},
};

export function savedTemplate(over: Record<string, unknown> = {}) {
  return {
    ...row(),
    terms: null,
    currency: "CAD",
    tax_mode: "exclusive",
    ship_to_country: "",
    ship_to_province: "",
    discount_type: "none",
    discount_value: "0.0000",
    notes: "For {{period_start}} to {{period_end}}",
    prorate: false,
    service_start: null,
    service_end: null,
    version: 1,
    created_by: "Dana Lee",
    unknown_placeholders: [],
    lines: [{ id: "rl1", ...line }],
    ...over,
  };
}

/** The next invoice as the generator builds it — and, once generated, the invoice itself. */
export const NEXT_INVOICE = {
  date: "2026-07-15",
  due_date: "2026-08-14",
  customer: { id: CUSTOMER, name: "Maple Leaf Supply Ltd." },
  reference: "Bookkeeping July 2026",
  notes: "For 15 Jul 2026 to 14 Aug 2026",
  tax_mode: "exclusive",
  discount_type: "none",
  discount_value: "0.0000",
  subtotal: "300.00",
  discount_total: "0.00",
  tax_total: "0.00",
  total: "300.00",
  lines: [
    {
      ...line,
      description: "Bookkeeping — July",
      net: "300.00",
      tax_amount: "0.00",
      amount: "300.00",
    },
  ],
  period: { start: "2026-07-15", end: "2026-08-14" },
  proration: { covered: 31, days: 31, full: true },
  skip: null,
};

export const RUNS = [
  {
    date: "2026-06-15",
    status: "created",
    code: "",
    message: "",
    version: 1,
    invoice: {
      id: INVOICE,
      number: "INV-0007",
      status: "approved",
      total: "339.00",
      url: `/o/${ORG}/sales/invoices/${INVOICE}`,
    },
  },
  {
    date: "2026-05-15",
    status: "skipped",
    code: "lock.violation",
    message: "The AR lock date is 31 May 2026.",
    version: 1,
    invoice: null,
  },
];

export interface RecurringState {
  current: Record<string, unknown>;
  posts: { path: string; body: Record<string, unknown> }[];
}

export async function mockRecurringInvoices(page: Page, initial = savedTemplate()) {
  await mockCsrf(page);
  const state: RecurringState = { current: initial, posts: [] };
  await page.route(`**/api/v1/o/${ORG}/accounts?*`, (r) =>
    r.fulfill({ json: { count: 1, results: [account] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/contacts?*`, (r) =>
    r.fulfill({
      json: {
        count: 1,
        next_offset: null,
        role_counts: {},
        results: [{ id: CUSTOMER, display_name: "Maple Leaf Supply Ltd.", roles: ["customer"] }],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/tax/codes*`, (r) => r.fulfill({ json: { results: [] } }));
  await page.route(`**/api/v1/o/${ORG}/recurring-invoices**`, async (r) => {
    const url = new URL(r.request().url());
    const path = url.pathname.replace(`/api/v1/o/${ORG}/recurring-invoices`, "");
    const method = r.request().method();
    if (path === "/schedule") return r.fulfill({ json: { dates: DATES } });
    if (path.endsWith("/preview"))
      return r.fulfill({ json: { invoice: NEXT_INVOICE, dates: DATES, status: "active" } });
    if (path.endsWith("/history"))
      return r.fulfill({
        json: { count: 2, page: 1, pages: 1, counts: { created: 1, skipped: 1 }, results: RUNS },
      });
    if (method === "POST" || method === "PATCH") {
      const body = (r.request().postDataJSON() ?? {}) as Record<string, unknown>;
      state.posts.push({ path: `${method} ${path}`, body });
      if (path === "") {
        state.current = savedTemplate({ ...body, customer: row().customer, lines: [line] });
        return r.fulfill({ status: 201, json: state.current });
      }
      if (path.endsWith("/pause"))
        state.current = { ...state.current, paused: true, status: "paused" };
      if (path.endsWith("/resume"))
        state.current = { ...state.current, paused: false, status: "active" };
      return r.fulfill({ json: state.current });
    }
    if (path === "")
      return r.fulfill({
        json: {
          count: 1,
          page: 1,
          pages: 1,
          counts: { active: 1, paused: 0, ended: 0 },
          results: [row()],
        },
      });
    return r.fulfill({ json: state.current });
  });
  await page.route(`**/api/v1/o/${ORG}/invoices/${INVOICE}`, (r) =>
    r.fulfill({ json: { id: INVOICE, number: "INV-0007", ...NEXT_INVOICE } }),
  );
  return state;
}
