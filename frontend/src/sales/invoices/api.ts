/**
 * Invoices API client (D-03a-T11): `/api/v1/o/<org>/invoices…` — drafts, the editor's preview
 * (journal, period ribbon, approval rule, credit check, duplicate suspects), approve / void /
 * copy.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export type InvoiceStatus =
  "draft" | "awaiting_approval" | "approved" | "sent" | "partially_paid" | "paid" | "void";
export type TaxMode = "exclusive" | "inclusive" | "no_tax";
export type DiscountType = "none" | "amount" | "percent";

export interface InvoiceLine {
  id: string;
  position: number;
  item: { id: string; name: string } | null;
  description: string;
  quantity: string;
  unit_price: string;
  discount_type: DiscountType;
  discount_value: string;
  account: { id: string; code: string; name: string } | null;
  tax_code: { id: string; code: string } | null;
  tax_overridden: boolean;
  tracking: Record<string, string>;
  net: string;
  tax_amount: string;
  amount: string;
}

export interface Invoice {
  id: string;
  number: string;
  status: InvoiceStatus;
  status_label: string;
  customer: { id: string; name: string };
  reference: string;
  date: string;
  due_date: string | null;
  total: string;
  amount_paid: string;
  amount_due: string;
  url: string;
  terms: string | null;
  currency: string;
  tax_mode: TaxMode;
  ship_to_country: string;
  ship_to_province: string;
  discount_type: DiscountType;
  discount_value: string;
  notes: string;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  version: number;
  journal: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  approved_by: string;
  sent_at: string | null;
  voided_at: string | null;
  pdf: string;
  attachments: { id: string; name: string }[];
  lines: InvoiceLine[];
  credit_warning?: string;
}

export interface InvoiceLineInput {
  description: string;
  quantity: string;
  unit_price: string;
  discount_type: DiscountType;
  discount_value: string;
  account: string | null;
  tax_code: string | null;
  tax_overridden?: boolean;
}

export interface InvoiceInput {
  customer: string;
  date: string;
  due_date?: string | null;
  reference: string;
  tax_mode: TaxMode;
  discount_type?: DiscountType;
  discount_value?: string;
  notes: string;
  lines: InvoiceLineInput[];
  attachments?: string[];
  version?: number;
}

export interface JournalRow {
  account: string;
  name: string;
  debit: string;
  credit: string;
  description: string;
}

export interface PeriodRibbon {
  date: string;
  ar_lock: string | null;
  locked: boolean;
  lock: { module: string; level: string; date: string } | null;
  tax_period: {
    start: string;
    end: string;
    status: string;
    filed: boolean;
    due_date: string;
  } | null;
}

export interface InvoicePreview {
  journal: {
    posted: boolean;
    complete: boolean;
    lines: JournalRow[];
    problem?: string;
  };
  period: PeriodRibbon;
  /** Why approval is needed (`threshold` / `limit`), or null. */
  approval: string | null;
  credit: { outcome: string; message: string };
  duplicates: unknown[];
}

export interface Refusal {
  code?: string;
  detail?: string;
  params?: Record<string, unknown>;
  [field: string]: unknown;
}

export interface InvoiceList {
  count: number;
  page: number;
  pages: number;
  counts: Record<InvoiceStatus, number>;
  results: Invoice[];
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/invoices`;
const one = (org: string, id: string) => `${base(org)}/${encodeURIComponent(id)}`;

type Result<T> = Promise<ApiResult<T>>;

export const invoicesApi = {
  list: (org: string, query: Record<string, string> = {}): Result<InvoiceList> => {
    const search = new URLSearchParams(query).toString();
    return apiRequest(search ? `${base(org)}?${search}` : base(org));
  },
  get: (org: string, id: string): Result<Invoice> => apiRequest(one(org, id)),
  create: (org: string, body: InvoiceInput): Result<Invoice & Refusal> =>
    apiRequest(base(org), { method: "POST", body }),
  update: (org: string, id: string, body: InvoiceInput): Result<Invoice & Refusal> =>
    apiRequest(one(org, id), { method: "PATCH", body }),
  remove: (org: string, id: string): Result<Refusal> =>
    apiRequest(one(org, id), { method: "DELETE" }),
  preview: (org: string, id: string): Result<InvoicePreview> =>
    apiRequest(`${one(org, id)}/preview`),
  approve: (org: string, id: string, lateAdjustment = false): Result<Invoice & Refusal> =>
    apiRequest(`${one(org, id)}/approve`, {
      method: "POST",
      body: lateAdjustment ? { late_adjustment: true } : {},
    }),
  void: (
    org: string,
    id: string,
    body: { date?: string; reason?: string },
  ): Result<Invoice & Refusal> => apiRequest(`${one(org, id)}/void`, { method: "POST", body }),
  copy: (
    org: string,
    id: string,
    to: "invoice" | "quote",
  ): Result<(Invoice | { id: string; number: string; url: string }) & Refusal> =>
    apiRequest(`${one(org, id)}/copy`, { method: "POST", body: { to } }),
};

export function invoiceUrl(org: string, id: string): string {
  return `/o/${org}/sales/invoices/${id}`;
}
