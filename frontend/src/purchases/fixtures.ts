/** Fixtures of the bill editor suites (E-02-T11…T14). */
import type { Bill, BillPreview } from "./api";

export { serveJson } from "@/banking/fixtures";

export const ORG = "acme";
export const SUPPLIER = "5a5a5a5a-0000-4000-8000-000000000001";
export const EXPENSE = "61006100-0000-4000-8000-000000000002";
export const HST_P = "cccc0001-0000-4000-8000-000000000001";
export const BILL_ID = "b1b1b1b1-0000-4000-8000-000000000001";
export const DOC_ID = "d0c0d0c0-0000-4000-8000-000000000001";

export const ACCOUNT = {
  id: EXPENSE,
  code: "6100",
  name: "Office supplies",
  type: "expense",
  subtype: "operating_expense",
  subtype_label: "",
  system_role: "",
  is_bank: false,
  depth: 1,
  has_children: false,
  require_contact: false,
  require_tracking: false,
  require_attachment: false,
  default_tax_key: "purchase.ON.standard",
};

export const TAX = {
  id: HST_P,
  code: "purchase.ON.standard",
  version: 1,
  name: "HST on purchases",
  side: "purchase",
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

export const DOCUMENT = {
  id: DOC_ID,
  name: "cedar-invoice-1001.pdf",
  mime: "application/pdf",
  size: 48213,
  sha256: "x",
  status: "clean",
  status_label: "Clean",
  source: "upload",
  sender: "",
  sender_known: false,
  period: "",
  tax_year: null,
  tags: [],
  folder: "inbox",
  preview_status: "ready",
  password_protected: false,
  uploaded_by: "Owner",
  created_at: "2026-06-15T12:00:00Z",
};

export const bill = (over: Partial<Bill> = {}): Bill => ({
  id: BILL_ID,
  number: "",
  status: "draft",
  status_label: "Draft",
  supplier: { id: SUPPLIER, name: "Cedar Supply Co." },
  supplier_invoice_no: "CS-1001",
  reference: "",
  date: "2026-06-15",
  due_date: "2026-07-15",
  total: "508.50",
  amount_due: "508.50",
  url: `/o/${ORG}/purchases/bills/${BILL_ID}`,
  terms: null,
  currency: "CAD",
  tax_mode: "exclusive",
  discount_type: "none",
  discount_value: "0.0000",
  department: "",
  notes: "",
  holdback_type: "none",
  holdback_value: "0.0000",
  holdback_amount: "0.00",
  holdback_released: "0.00",
  holdback_outstanding: "0.00",
  subtotal: "450.00",
  discount_total: "0.00",
  tax_total: "58.50",
  amount_paid: "0.00",
  version: 1,
  purchase_order: null,
  journal: null,
  lines: [
    {
      id: "l1",
      position: 0,
      description: "Tiles",
      quantity: "10.0000",
      unit_price: "45.0000",
      discount_type: "none",
      discount_value: "0.0000",
      account: { id: EXPENSE, code: "6100", name: "Office supplies" },
      tax_code: { id: HST_P, code: "purchase.ON.standard" },
      tracking: {},
      po_line: null,
      net: "450.00",
      tax_amount: "58.50",
      amount: "450.00",
    },
  ],
  ...over,
});

export const PREVIEW: BillPreview = {
  journal: { lines: [], complete: true },
  itc: [{ tax: "58.50", claimable: "58.50", cost: "0.00" }],
  routing: { rule: null, role: null, role_name: null, explanation: "" },
  duplicates: [],
  match: [],
};

/** The editor's reference data and the bill endpoints; `extra` answers first. */
export function billHandler(
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
          results: [{ id: SUPPLIER, display_name: "Cedar Supply Co.", roles: ["supplier"] }],
        },
      };
    if (url.includes("/tax/codes")) return { body: { results: [TAX] } };
    if (url.includes("/calculate")) return { status: 503, body: {} };
    if (url.includes(`/files/${DOC_ID}/url`))
      return { body: { url: `/__file/${DOC_ID}.pdf`, expires_at: "" } };
    if (url.includes("/__file/")) return { body: "%PDF-1.4" };
    if (url.includes(`/files/${DOC_ID}`)) return { body: DOCUMENT };
    if (url.includes("/files/attachments")) return { body: { results: [] } };
    if (url.includes("/check-number"))
      return { body: { number: "", available: true, conflict: null } };
    if (url.endsWith("/preview")) return { body: PREVIEW };
    if (url.endsWith("/bills") && method === "POST") return { status: 201, body: bill() };
    if (url.endsWith(`/bills/${BILL_ID}`) && method === "PATCH")
      return { body: bill({ version: 2 }) };
    if (url.endsWith(`/bills/${BILL_ID}`)) return { body: bill() };
    if (url.endsWith("/approve"))
      return {
        body: bill({
          status: "awaiting_payment",
          status_label: "Awaiting payment",
          number: "BILL-0001",
        }),
      };
    if (url.endsWith("/submit"))
      return { body: bill({ status: "awaiting_approval", status_label: "Awaiting approval" }) };
    return { status: 404, body: {} };
  };
}
