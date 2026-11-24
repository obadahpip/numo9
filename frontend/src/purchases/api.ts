/**
 * Bills API client (E-02-T10): `/api/v1/o/<org>/bills…` — drafts, the editor's preview (journal,
 * ITC split, routing, duplicate suspects, PO match panel), submit / approve / void / release
 * holdback, the live supplier-invoice-number check.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export type BillStatus =
  "draft" | "awaiting_approval" | "awaiting_payment" | "partially_paid" | "paid" | "void";
export type HoldbackType = "none" | "amount" | "percent";
export type TaxMode = "exclusive" | "inclusive" | "no_tax";

export interface BillLine {
  id: string;
  position: number;
  description: string;
  quantity: string;
  unit_price: string;
  discount_type: "none" | "amount" | "percent";
  discount_value: string;
  account: { id: string; code: string; name: string } | null;
  tax_code: { id: string; code: string } | null;
  tracking: Record<string, string>;
  po_line: string | null;
  net: string;
  tax_amount: string;
  amount: string;
}

export interface Bill {
  id: string;
  number: string;
  status: BillStatus;
  status_label: string;
  supplier: { id: string; name: string };
  supplier_invoice_no: string;
  reference: string;
  date: string;
  due_date: string | null;
  total: string;
  amount_due: string;
  url: string;
  terms: string | null;
  currency: string;
  tax_mode: TaxMode;
  discount_type: "none" | "amount" | "percent";
  discount_value: string;
  department: string;
  notes: string;
  holdback_type: HoldbackType;
  holdback_value: string;
  holdback_amount: string;
  holdback_released: string;
  holdback_outstanding: string;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  amount_paid: string;
  version: number;
  purchase_order: { id: string; number: string } | null;
  journal: string | null;
  lines: BillLine[];
}

export interface BillLineInput {
  description: string;
  quantity: string;
  unit_price: string;
  discount_type: "none" | "amount" | "percent";
  discount_value: string;
  account: string | null;
  tax_code: string | null;
  po_line?: string | null;
}

export interface BillInput {
  supplier: string;
  date: string;
  due_date?: string | null;
  supplier_invoice_no: string;
  reference: string;
  tax_mode: TaxMode;
  department: string;
  notes: string;
  holdback_type: HoldbackType;
  holdback_value: string;
  lines: BillLineInput[];
  document?: string | null;
  version?: number;
}

export interface MatchRow {
  line: string;
  po_line: string;
  po: string;
  description: string;
  ordered: string;
  received: string;
  billed_elsewhere: string;
  quantity: string;
  po_price: string;
  price: string;
  quantity_over: string;
  price_difference_pct: string;
  status: "green" | "amber" | "red";
}

export interface DuplicateSuspect {
  id: string;
  number: string;
  supplier_invoice_no: string;
  date: string;
  total: string;
  status: BillStatus;
  days_apart: number;
  message: string;
}

export interface BillPreview {
  journal: {
    lines: { account: string; name: string; debit: string; credit: string; description: string }[];
    complete: boolean;
    problem?: string;
  };
  itc: { tax: string; claimable: string; cost: string }[];
  routing: {
    rule: string | null;
    role: string | null;
    role_name: string | null;
    explanation: string;
  };
  duplicates: DuplicateSuspect[];
  match: MatchRow[];
}

export interface NumberCheck {
  number: string;
  available: boolean;
  conflict: {
    id: string;
    number: string;
    status: BillStatus;
    date: string;
    url: string;
    message: string;
  } | null;
}

export interface Refusal {
  code?: string;
  detail?: string;
  supplier_invoice_no?: string[];
  [field: string]: unknown;
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/bills`;
type Result<T> = Promise<ApiResult<T & Refusal>>;

export const billsApi = {
  get: (org: string, id: string): Result<Bill> => apiRequest(`${base(org)}/${id}`),
  create: (org: string, body: BillInput): Result<Bill> =>
    apiRequest(base(org), { method: "POST", body }),
  update: (org: string, id: string, body: BillInput): Result<Bill> =>
    apiRequest(`${base(org)}/${id}`, { method: "PATCH", body }),
  preview: (org: string, id: string): Result<BillPreview> =>
    apiRequest(`${base(org)}/${id}/preview`),
  submit: (org: string, id: string): Result<Bill> =>
    apiRequest(`${base(org)}/${id}/submit`, { method: "POST" }),
  approve: (org: string, id: string, withVariance = false): Result<Bill> =>
    apiRequest(`${base(org)}/${id}/approve`, {
      method: "POST",
      body: { with_variance: withVariance },
    }),
  checkNumber: (
    org: string,
    supplier: string,
    number: string,
    exclude?: string,
  ): Result<NumberCheck> => {
    const query = new URLSearchParams({ supplier, number });
    if (exclude) query.set("exclude", exclude);
    return apiRequest(`${base(org)}/check-number?${query.toString()}`);
  },
};
