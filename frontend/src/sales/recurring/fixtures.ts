/** Fixtures of the recurring invoice suites (D-04-T08…T10): the shapes of recurring_api.py. */
import { ACCOUNT, CUSTOMER, HST_S, ORG, REVENUE, TAX } from "../invoices/fixtures";
import type {
  PreviewInvoice,
  RecurringPreview,
  RecurringRow,
  RecurringRun,
  RecurringTemplate,
} from "./api";

export { serveJson } from "@/banking/fixtures";
export { CUSTOMER, ORG, REVENUE };

export const TEMPLATE_ID = "2c2c2c2c-0000-4000-8000-000000000001";

export const row = (over: Partial<RecurringRow> = {}): RecurringRow => ({
  id: TEMPLATE_ID,
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
  skipped: 0,
  url: `/o/${ORG}/sales/recurring-invoices/${TEMPLATE_ID}`,
  ...over,
});

export const template = (over: Partial<RecurringTemplate> = {}): RecurringTemplate => ({
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
  lines: [
    {
      id: "rl1",
      position: 0,
      item: null,
      description: "Bookkeeping — {{month}}",
      quantity: "1.0000",
      unit_price: "300.0000",
      discount_type: "none",
      discount_value: "0.0000",
      account: { id: REVENUE, code: "4000", name: "Sales" },
      tax_code: { id: HST_S, code: "sales.ON.standard" },
      tax_overridden: false,
      tracking: {},
    },
  ],
  ...over,
});

export const previewInvoice = (over: Partial<PreviewInvoice> = {}): PreviewInvoice => ({
  date: "2026-07-15",
  due_date: "2026-08-14",
  customer: { id: CUSTOMER, name: "Maple Leaf Supply Ltd." },
  reference: "Bookkeeping July 2026",
  notes: "For 15 Jul 2026 to 14 Aug 2026",
  tax_mode: "exclusive",
  subtotal: "300.00",
  discount_total: "0.00",
  tax_total: "39.00",
  total: "339.00",
  lines: [
    {
      position: 0,
      item: null,
      description: "Bookkeeping — July",
      quantity: "1.0000",
      unit_price: "300.0000",
      discount_type: "none",
      discount_value: "0.0000",
      account: { id: REVENUE, code: "4000", name: "Sales" },
      tax_code: { id: HST_S, code: "sales.ON.standard" },
      tax_overridden: false,
      tracking: {},
      net: "300.00",
      tax_amount: "39.00",
      amount: "300.00",
    },
  ],
  period: { start: "2026-07-15", end: "2026-08-14" },
  proration: { covered: 31, days: 31, full: true },
  skip: null,
  ...over,
});

export const PREVIEW: RecurringPreview = {
  invoice: previewInvoice(),
  dates: ["2026-07-15", "2026-08-15", "2026-09-15", "2026-10-15", "2026-11-15", "2026-12-15"],
  status: "active",
};

export const RUNS: RecurringRun[] = [
  {
    date: "2026-06-15",
    status: "created",
    code: "",
    message: "",
    version: 1,
    invoice: {
      id: "1a1a1a1a-0000-4000-8000-000000000001",
      number: "INV-0007",
      status: "approved",
      total: "339.00",
      url: `/o/${ORG}/sales/invoices/1a1a1a1a-0000-4000-8000-000000000001`,
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

/** The editor's reference data and the recurring endpoints; `extra` answers first. */
export function recurringHandler(
  calls: { url: string; method: string; body: unknown }[],
  extra?: (url: string, method: string) => { status?: number; body: unknown } | undefined,
) {
  return (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : null });
    const special = extra?.(url, method);
    if (special) return special;
    if (url.includes("/accounts?")) return { body: { count: 1, results: [ACCOUNT] } };
    if (url.includes("/contacts?"))
      return {
        body: {
          count: 1,
          next_offset: null,
          role_counts: {},
          results: [{ id: CUSTOMER, display_name: "Maple Leaf Supply Ltd.", roles: ["customer"] }],
        },
      };
    if (url.includes("/tax/codes")) return { body: { results: [TAX] } };
    if (url.includes("/calculate")) return { status: 503, body: {} };
    if (url.endsWith("/recurring-invoices/schedule")) return { body: { dates: PREVIEW.dates } };
    if (url.includes("/preview")) return { body: PREVIEW };
    if (url.includes("/history"))
      return {
        body: { count: 2, page: 1, pages: 1, counts: { created: 1, skipped: 1 }, results: RUNS },
      };
    if (url.endsWith("/pause")) return { body: template({ paused: true, status: "paused" }) };
    if (url.endsWith("/resume")) return { body: template() };
    if (url.endsWith("/recurring-invoices") && method === "POST")
      return { status: 201, body: template() };
    if (url.endsWith(`/recurring-invoices/${TEMPLATE_ID}`) && method === "PATCH")
      return { body: template({ version: 2 }) };
    if (url.endsWith(`/recurring-invoices/${TEMPLATE_ID}`)) return { body: template() };
    if (url.includes("/recurring-invoices"))
      return {
        body: {
          count: 1,
          page: 1,
          pages: 1,
          counts: { active: 1, paused: 0, ended: 0 },
          results: [row()],
        },
      };
    return { status: 404, body: {} };
  };
}
