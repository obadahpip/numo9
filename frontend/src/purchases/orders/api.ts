/**
 * Purchase orders API client (E-01-T10): `/api/v1/o/<org>/purchase-orders…` (drafts, approval
 * within the limit, cancel / close, the 3-way match), `/receipts…` (goods receipts and their
 * reversal) and `/reports/commitments` (open PO value, with its CSV / XLSX export).
 */
import { apiRequest, type ApiResult } from "@/auth/client";

import type { Refusal, TaxMode } from "../api";

export type { Refusal, TaxMode } from "../api";

export type PurchaseOrderStatus =
  | "draft"
  | "awaiting_approval"
  | "approved"
  | "partially_received"
  | "received"
  | "billed"
  | "closed"
  | "cancelled";

export const PO_STATUSES: readonly PurchaseOrderStatus[] = [
  "draft",
  "awaiting_approval",
  "approved",
  "partially_received",
  "received",
  "billed",
  "closed",
  "cancelled",
];

export interface PurchaseOrderLine {
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
  quantity_received: string;
  quantity_billed: string;
  outstanding: string;
  net: string;
  tax_amount: string;
  amount: string;
}

export interface PurchaseOrderRow {
  id: string;
  number: string;
  status: PurchaseOrderStatus;
  status_label: string;
  supplier: { id: string; name: string };
  reference: string;
  date: string;
  delivery_date: string | null;
  total: string;
  url: string;
}

export interface ReceiptRow {
  id: string;
  purchase_order: { id: string; number: string };
  date: string;
  received_by: string;
  notes: string;
  reversed_at: string | null;
  reversal_reason: string;
  lines?: { po_line: string; description: string; quantity: string }[];
}

export interface PurchaseOrder extends PurchaseOrderRow {
  terms: string | null;
  currency: string;
  tax_mode: TaxMode;
  discount_type: "none" | "amount" | "percent";
  discount_value: string;
  notes: string;
  delivery_attention: string;
  delivery_address: string;
  delivery_instructions: string;
  subtotal: string;
  discount_total: string;
  tax_total: string;
  approved_total: string | null;
  version: number;
  submitted_at: string | null;
  approved_at: string | null;
  approved_by: string;
  sent_at: string | null;
  /** The limit indicator: the person's purchase-order approval limit and the total within it. */
  approval: { limit: string | null; within: boolean };
  lines: PurchaseOrderLine[];
  receipts: ReceiptRow[];
}

export interface PurchaseOrderLineInput {
  id?: string | null;
  description: string;
  quantity: string;
  unit_price: string;
  discount_type: "none" | "amount" | "percent";
  discount_value: string;
  account: string | null;
  tax_code: string | null;
}

export interface PurchaseOrderInput {
  supplier: string;
  date: string;
  reference: string;
  tax_mode: TaxMode;
  notes: string;
  delivery_attention: string;
  delivery_address: string;
  delivery_date: string | null;
  delivery_instructions: string;
  lines: PurchaseOrderLineInput[];
  version?: number;
}

export interface PurchaseOrderList {
  count: number;
  page: number;
  pages: number;
  counts: Record<PurchaseOrderStatus, number>;
  results: PurchaseOrderRow[];
}

export interface OverReceipt {
  line: string;
  ordered: string;
  received: string;
  allowed: string;
}

export interface ReceiptInput {
  purchase_order: string;
  date?: string | null;
  notes?: string;
  lines: { po_line: string; quantity: string }[];
  confirm_over?: boolean;
}

export interface ReceiptResult extends ReceiptRow {
  warnings: OverReceipt[];
  purchase_order_status: PurchaseOrderStatus;
}

export type MatchStatus = "green" | "amber" | "red";

export interface OrderMatchLine {
  line: string;
  description: string;
  ordered: string;
  received: string;
  outstanding: string;
  billed: string;
  pending: string;
  to_bill: string;
  po_price: string;
  flags: string[];
  status: MatchStatus;
  bills: {
    id: string;
    number: string;
    status: string;
    date: string;
    url: string;
    quantity: string;
    price: string;
    match: MatchStatus;
  }[];
}

export interface OrderMatch {
  purchase_order: { id: string; number: string; status: PurchaseOrderStatus };
  tolerance: { quantity: string; price: string };
  status: MatchStatus;
  lines: OrderMatchLine[];
}

export type CommitmentGrouping = "account" | "supplier" | "month";

export interface CommitmentReport {
  by: CommitmentGrouping;
  rows: {
    key: string;
    label: string;
    amount: string;
    lines: number;
    orders: number;
    budget: string | null;
  }[];
  total: string;
  from: string | null;
  to: string | null;
}

export interface CommitmentQuery {
  by: CommitmentGrouping;
  from?: string;
  to?: string;
}

const root = (org: string) => `/api/v1/o/${encodeURIComponent(org)}`;
const base = (org: string) => `${root(org)}/purchase-orders`;
type Result<T> = Promise<ApiResult<T & Refusal>>;

function commitmentQuery(query: CommitmentQuery, exported?: "csv" | "xlsx"): string {
  const params = new URLSearchParams({ by: query.by });
  if (query.from) params.set("from", query.from);
  if (query.to) params.set("to", query.to);
  if (exported) params.set("export", exported);
  return params.toString();
}

export const purchaseOrdersApi = {
  list: (
    org: string,
    query: { status?: string; q?: string; page?: number } = {},
  ): Result<PurchaseOrderList> => {
    const params = new URLSearchParams();
    if (query.status) params.set("status", query.status);
    if (query.q) params.set("q", query.q);
    if (query.page && query.page > 1) params.set("page", String(query.page));
    const text = params.toString();
    return apiRequest(text ? `${base(org)}?${text}` : base(org));
  },
  get: (org: string, id: string): Result<PurchaseOrder> => apiRequest(`${base(org)}/${id}`),
  approvalLimit: (org: string): Result<{ limit: string | null }> =>
    apiRequest(`${base(org)}/approval-limit`),
  create: (org: string, body: PurchaseOrderInput): Result<PurchaseOrder> =>
    apiRequest(base(org), { method: "POST", body }),
  update: (org: string, id: string, body: PurchaseOrderInput): Result<PurchaseOrder> =>
    apiRequest(`${base(org)}/${id}`, { method: "PATCH", body }),
  action: (
    org: string,
    id: string,
    action: "submit" | "approve" | "cancel" | "close",
  ): Result<PurchaseOrder> => apiRequest(`${base(org)}/${id}/${action}`, { method: "POST" }),
  match: (org: string, id: string): Result<OrderMatch> => apiRequest(`${base(org)}/${id}/match`),
  pdfUrl: (org: string, id: string) => `${base(org)}/${id}/pdf`,
  billFromOrder: (org: string, id: string): Result<{ id: string; url: string }> =>
    apiRequest(`${root(org)}/bills/from-po`, { method: "POST", body: { purchase_order: id } }),
};

export const receiptsApi = {
  create: (org: string, body: ReceiptInput): Result<ReceiptResult> =>
    apiRequest(`${root(org)}/receipts`, { method: "POST", body }),
  reverse: (org: string, id: string, reason: string): Result<ReceiptRow> =>
    apiRequest(`${root(org)}/receipts/${id}/reverse`, { method: "POST", body: { reason } }),
};

export const commitmentsApi = {
  get: (org: string, query: CommitmentQuery): Result<CommitmentReport> =>
    apiRequest(`${root(org)}/reports/commitments?${commitmentQuery(query)}`),
  exportUrl: (org: string, query: CommitmentQuery, format: "csv" | "xlsx") =>
    `${root(org)}/reports/commitments?${commitmentQuery(query, format)}`,
};
