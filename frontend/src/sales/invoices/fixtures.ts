/** Fixtures of the invoice editor suites (D-03a-T13, T14). */
import type { Invoice, InvoicePreview } from "./api";

export { serveJson } from "@/banking/fixtures";

export const ORG = "acme";
export const CUSTOMER = "c0c0c0c0-0000-4000-8000-000000000001";
export const REVENUE = "40004000-0000-4000-8000-000000000002";
export const HST_S = "cccc0002-0000-4000-8000-000000000001";
export const INVOICE_ID = "1a1a1a1a-0000-4000-8000-000000000001";

export const ACCOUNT = {
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
  default_tax_key: "sales.ON.standard",
};

export const TAX = {
  id: HST_S,
  code: "sales.ON.standard",
  version: 1,
  name: "HST on sales",
  side: "sales",
  type: "taxable",
  province: "ON",
  effective_from: "2016-07-01",
  effective_to: null,
  expired: false,
  archived_at: null,
  rate: "13",
  components: [
    { id: "c1", key: "hst_on", name: "HST", kind: "hst", rate: "13", recoverable_pct: null },
  ],
};

export const invoice = (over: Partial<Invoice> = {}): Invoice => ({
  id: INVOICE_ID,
  number: "",
  status: "draft",
  status_label: "Draft",
  customer: { id: CUSTOMER, name: "Maple Leaf Supply Ltd." },
  reference: "PO-778",
  date: "2026-06-15",
  due_date: "2026-07-15",
  total: "565.00",
  amount_paid: "0.00",
  amount_due: "565.00",
  url: `/o/${ORG}/sales/invoices/${INVOICE_ID}`,
  terms: null,
  currency: "CAD",
  tax_mode: "exclusive",
  ship_to_country: "",
  ship_to_province: "",
  discount_type: "none",
  discount_value: "0.0000",
  notes: "",
  subtotal: "500.00",
  discount_total: "0.00",
  tax_total: "65.00",
  version: 1,
  journal: null,
  submitted_at: null,
  approved_at: null,
  approved_by: "",
  sent_at: null,
  voided_at: null,
  pdf: `/api/v1/o/${ORG}/invoices/${INVOICE_ID}/pdf`,
  attachments: [],
  lines: [
    {
      id: "l1",
      position: 0,
      item: null,
      description: "Design consultation",
      quantity: "2.0000",
      unit_price: "250.0000",
      discount_type: "none",
      discount_value: "0.0000",
      account: { id: REVENUE, code: "4000", name: "Sales" },
      tax_code: { id: HST_S, code: "sales.ON.standard" },
      tax_overridden: false,
      tracking: {},
      net: "500.00",
      tax_amount: "65.00",
      amount: "500.00",
    },
  ],
  ...over,
});

export const PREVIEW: InvoicePreview = {
  journal: {
    posted: false,
    complete: true,
    lines: [
      {
        account: "1200",
        name: "Accounts receivable",
        debit: "565.00",
        credit: "0.00",
        description: "",
      },
      { account: "4000", name: "Sales", debit: "0.00", credit: "500.00", description: "" },
      { account: "2200", name: "GST/HST payable", debit: "0.00", credit: "65.00", description: "" },
    ],
  },
  period: {
    date: "2026-06-15",
    ar_lock: "2026-03-31",
    locked: false,
    lock: null,
    tax_period: {
      start: "2026-04-01",
      end: "2026-06-30",
      status: "open",
      filed: false,
      due_date: "2026-07-31",
    },
  },
  approval: null,
  credit: { outcome: "no_limit", message: "" },
  duplicates: [],
};

/** The editor's reference data and the invoice endpoints; `extra` answers first. */
export function invoiceHandler(
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
    if (url.includes("/credit")) return { body: { outcome: "no_limit" } };
    if (url.endsWith("/preview")) return { body: PREVIEW };
    if (url.endsWith("/invoices") && method === "POST") return { status: 201, body: invoice() };
    if (url.endsWith(`/invoices/${INVOICE_ID}`) && method === "PATCH")
      return { body: invoice({ version: 2 }) };
    if (url.endsWith(`/invoices/${INVOICE_ID}`)) return { body: invoice() };
    if (url.endsWith("/approve"))
      return {
        body: invoice({
          status: "approved",
          status_label: "Approved",
          number: "INV-0001",
          journal: `/o/${ORG}/accounting/journals/j1`,
        }),
      };
    return { status: 404, body: {} };
  };
}
