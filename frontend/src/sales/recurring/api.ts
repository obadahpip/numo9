/**
 * Recurring invoices API client (D-04-T07): `/api/v1/o/<org>/recurring-invoices…` — the
 * templates (list with next / last run and status, CRUD with the version check), pause / resume,
 * the preview of the next invoice (placeholders resolved, built by the generator itself), the
 * history of generated invoices and skipped dates, and the schedule panel's dates.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

import type {
  DiscountType,
  InvoiceLine,
  InvoiceLineInput,
  Refusal,
  TaxMode,
} from "../invoices/api";

export type RecurringMode = "draft" | "approve" | "approve_send";
export type RecurringStatus = "active" | "paused" | "ended";

export interface RecurringRow {
  id: string;
  name: string;
  status: RecurringStatus;
  customer: { id: string; name: string };
  reference: string;
  mode: RecurringMode;
  rrule: string;
  start_date: string;
  end_date: string | null;
  next_run: string | null;
  last_run: string | null;
  paused: boolean;
  generated: number;
  skipped: number;
  url: string;
}

/** A template line: the invoice line without figures (the preview calculates them). */
export type RecurringLine = Omit<InvoiceLine, "net" | "tax_amount" | "amount">;

export interface RecurringTemplate extends RecurringRow {
  terms: string | null;
  currency: string;
  tax_mode: TaxMode;
  ship_to_country: string;
  ship_to_province: string;
  discount_type: DiscountType;
  discount_value: string;
  notes: string;
  prorate: boolean;
  service_start: string | null;
  service_end: string | null;
  version: number;
  created_by: string;
  unknown_placeholders: string[];
  lines: RecurringLine[];
}

export interface RecurringInput {
  name: string;
  customer: string;
  reference: string;
  tax_mode: TaxMode;
  notes: string;
  rrule: string;
  start_date: string;
  end_date: string | null;
  mode: RecurringMode;
  prorate: boolean;
  service_start: string | null;
  service_end: string | null;
  paused?: boolean;
  lines: InvoiceLineInput[];
  version?: number;
}

export interface PreviewInvoice {
  date: string;
  due_date: string | null;
  customer: { id: string; name: string };
  reference: string;
  notes: string;
  tax_mode: TaxMode;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  total: string;
  lines: Omit<InvoiceLine, "id">[];
  period: { start: string; end: string };
  proration: { covered: number; days: number; full: boolean };
  skip: { code: string; message: string } | null;
}

export interface RecurringPreview {
  invoice: PreviewInvoice | null;
  dates: string[];
  status: RecurringStatus;
}

export interface RecurringRun {
  date: string;
  status: "created" | "skipped";
  code: string;
  message: string;
  version: number;
  invoice: { id: string; number: string; status: string; total: string; url: string } | null;
}

export interface Page<T, C extends string> {
  count: number;
  page: number;
  pages: number;
  counts: Record<C, number>;
  results: T[];
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/recurring-invoices`;
const one = (org: string, id: string) => `${base(org)}/${encodeURIComponent(id)}`;

type Result<T> = Promise<ApiResult<T>>;

export const recurringInvoicesApi = {
  list: (
    org: string,
    query: Record<string, string> = {},
  ): Result<Page<RecurringRow, RecurringStatus>> => {
    const search = new URLSearchParams(query).toString();
    return apiRequest(search ? `${base(org)}?${search}` : base(org));
  },
  get: (org: string, id: string): Result<RecurringTemplate> => apiRequest(one(org, id)),
  create: (org: string, body: RecurringInput): Result<RecurringTemplate & Refusal> =>
    apiRequest(base(org), { method: "POST", body }),
  update: (org: string, id: string, body: RecurringInput): Result<RecurringTemplate & Refusal> =>
    apiRequest(one(org, id), { method: "PATCH", body }),
  remove: (org: string, id: string): Result<Refusal> =>
    apiRequest(one(org, id), { method: "DELETE" }),
  pause: (org: string, id: string): Result<RecurringTemplate & Refusal> =>
    apiRequest(`${one(org, id)}/pause`, { method: "POST", body: {} }),
  resume: (org: string, id: string): Result<RecurringTemplate & Refusal> =>
    apiRequest(`${one(org, id)}/resume`, { method: "POST", body: {} }),
  preview: (org: string, id: string, date?: string): Result<RecurringPreview & Refusal> =>
    apiRequest(
      date ? `${one(org, id)}/preview?${new URLSearchParams({ date })}` : `${one(org, id)}/preview`,
    ),
  history: (org: string, id: string, page = 1): Result<Page<RecurringRun, "created" | "skipped">> =>
    apiRequest(`${one(org, id)}/history?page=${page}`),
  /** The next dates of an unsaved schedule (the generator's engine). */
  schedule: (
    org: string,
    body: { rrule: string; start_date: string; end_date: string | null; count: number },
  ): Result<{ dates: string[] } & Refusal> =>
    apiRequest(`${base(org)}/schedule`, { method: "POST", body }),
};

export function recurringUrl(org: string, id?: string): string {
  return id ? `/o/${org}/sales/recurring-invoices/${id}` : `/o/${org}/sales/recurring-invoices`;
}
