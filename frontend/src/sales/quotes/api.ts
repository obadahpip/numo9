/**
 * Quotes API client (D-02-T11): `/api/v1/o/<org>/quotes…` — drafts, the list with its counts per
 * status and per tab, send / link / accept / decline / invoice / copy / revise; and the public
 * link's `/api/v1/q/<token>…` endpoints (view, live totals of the options ticked, accept with
 * evidence, decline).
 */
import { apiRequest, type ApiResult } from "@/auth/client";

import type { DiscountType, InvoiceLine, Refusal, TaxMode } from "../invoices/api";
import type { QuoteStatus } from "./status";

export type { QuoteStatus } from "./status";
export type DepositType = "none" | "amount" | "percent";

/** The list tabs (D-02-T14): the QuoteStatus values, Sent covering sent and viewed quotes. */
export const QUOTE_TABS = [
  "all",
  "draft",
  "sent",
  "accepted",
  "declined",
  "expired",
  "invoiced",
] as const;
export type QuoteTab = (typeof QUOTE_TABS)[number];

export interface QuoteLine extends InvoiceLine {
  is_optional: boolean;
  alternative_group: string;
  selected: boolean;
  counted: boolean;
}

interface Ref {
  id: string;
  number: string;
  url: string;
}

export interface QuoteSummary {
  id: string;
  number: string;
  status: QuoteStatus;
  status_label: string;
  title: string;
  customer: { id: string; name: string };
  reference: string;
  date: string;
  expiry_date: string;
  total: string;
  url: string;
}

export interface Quote extends QuoteSummary {
  summary: string;
  currency: string;
  tax_mode: TaxMode;
  ship_to_country: string;
  ship_to_province: string;
  discount_type: DiscountType;
  discount_value: string;
  deposit_type: DepositType;
  deposit_value: string;
  deposit_amount: string;
  notes: string;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  version: number;
  sent_at: string | null;
  viewed_at: string | null;
  accepted_at: string | null;
  declined_at: string | null;
  decline_reason: string;
  expired_at: string | null;
  invoiced_at: string | null;
  invoice: Ref | null;
  deposit_invoice: (Ref & { status: string; total: string }) | null;
  revises: Ref | null;
  superseded_by: Ref | null;
  link: { url: string; views: number; last_viewed_at: string | null } | null;
  acceptance: {
    typed_name: string;
    signed: boolean;
    ip: string | null;
    user_agent: string;
    accepted_at: string;
    pdf_sha256: string;
  } | null;
  pdf: string;
  lines: QuoteLine[];
}

export interface QuoteLineInput {
  description: string;
  quantity: string;
  unit_price: string;
  discount_type: DiscountType;
  discount_value: string;
  account: string | null;
  tax_code: string | null;
  tax_overridden?: boolean;
  is_optional: boolean;
  alternative_group: string;
  selected: boolean;
}

export interface QuoteInput {
  customer: string;
  date: string;
  expiry_date: string;
  title: string;
  summary: string;
  reference: string;
  tax_mode: TaxMode;
  deposit_type: DepositType;
  deposit_value: string;
  notes: string;
  lines: QuoteLineInput[];
  version?: number;
}

export interface QuoteList {
  count: number;
  page: number;
  pages: number;
  counts: Record<QuoteStatus, number>;
  tabs: Record<QuoteTab, number>;
  results: QuoteSummary[];
}

/** Why the public page can't take an acceptance, or null when it can. */
export type PublicReason =
  "superseded" | "accepted" | "declined" | "expired" | "invoiced" | "not_sent";

export interface PublicQuoteLine {
  id: string;
  description: string;
  quantity: string;
  unit_price: string;
  amount: string;
  tax: string;
  is_optional: boolean;
  alternative_group: string;
  selected: boolean;
  counted: boolean;
}

export interface PublicQuote {
  number: string;
  title: string;
  summary: string;
  organisation: string;
  customer: string;
  date: string;
  expiry_date: string;
  currency: string;
  status: QuoteStatus;
  lines: PublicQuoteLine[];
  subtotal: string;
  discount_total: string;
  tax_total: string;
  total: string;
  deposit_type: DepositType;
  deposit_value: string;
  deposit: string;
  accepted_by: string | null;
  can_accept: boolean;
  reason: PublicReason | null;
}

export interface SelectionTotals {
  lines: Record<string, { selected: boolean; counted: boolean }>;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  total: string;
  deposit: string;
}

export interface AcceptInput {
  typed_name: string;
  /** A `data:image/png;base64,…` URL, or empty: the typed name alone accepts. */
  signature: string;
  selections: Record<string, boolean>;
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/quotes`;
const one = (org: string, id: string) => `${base(org)}/${encodeURIComponent(id)}`;
const pub = (token: string) => `/api/v1/q/${encodeURIComponent(token)}`;

type Result<T> = Promise<ApiResult<T>>;
const post = <T>(url: string, body: unknown = {}): Result<T> =>
  apiRequest(url, { method: "POST", body });

export const quotesApi = {
  list: (org: string, query: Record<string, string> = {}): Result<QuoteList> => {
    const search = new URLSearchParams(query).toString();
    return apiRequest(search ? `${base(org)}?${search}` : base(org));
  },
  get: (org: string, id: string): Result<Quote> => apiRequest(one(org, id)),
  create: (org: string, body: QuoteInput): Result<Quote & Refusal> => post(base(org), body),
  update: (org: string, id: string, body: QuoteInput): Result<Quote & Refusal> =>
    apiRequest(one(org, id), { method: "PATCH", body }),
  remove: (org: string, id: string): Result<Refusal> =>
    apiRequest(one(org, id), { method: "DELETE" }),
  send: (
    org: string,
    id: string,
    body: { email: false } | { to?: string[]; message?: string },
  ): Result<Quote & Refusal> => post(`${one(org, id)}/send`, body),
  link: (org: string, id: string): Result<Quote & Refusal> => post(`${one(org, id)}/link`),
  revokeLinks: (org: string, id: string): Result<Quote & Refusal> =>
    apiRequest(`${one(org, id)}/link`, { method: "DELETE" }),
  accept: (org: string, id: string): Result<Quote & Refusal> => post(`${one(org, id)}/accept`),
  decline: (org: string, id: string, reason = ""): Result<Quote & Refusal> =>
    post(`${one(org, id)}/decline`, { reason }),
  invoice: (org: string, id: string): Result<{ id: string; url: string } & Refusal> =>
    post(`${one(org, id)}/invoice`),
  revise: (org: string, id: string): Result<Quote & Refusal> => post(`${one(org, id)}/revise`),
  copy: (org: string, id: string, to: "quote" | "invoice"): Result<{ id: string; url: string }> =>
    post(`${one(org, id)}/copy`, { to }),
};

export const publicQuoteApi = {
  get: (token: string): Result<PublicQuote & Refusal> => apiRequest(pub(token)),
  preview: (token: string, selections: Record<string, boolean>): Result<SelectionTotals> =>
    post(`${pub(token)}/preview`, { selections }),
  accept: (token: string, body: AcceptInput): Result<PublicQuote & Refusal> =>
    post(`${pub(token)}/accept`, body),
  decline: (token: string, reason: string): Result<PublicQuote & Refusal> =>
    post(`${pub(token)}/decline`, { reason }),
  pdfUrl: (token: string) => `${pub(token)}/pdf`,
};

export function quoteUrl(org: string, id: string): string {
  return `/o/${org}/sales/quotes/${id}`;
}
