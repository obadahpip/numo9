/** Bulk actions API (V-03-T07): preview, confirm, cancel, status, rows, files. */
import { apiRequest, type ApiResult } from "@/auth/client";

import type { BulkActionKey } from "./SelectionBar";

export const BULK_URL = "/api/v1/practice/bulk";

export type BulkStatus = "preview" | "queued" | "running" | "completed" | "cancelled";
export type RowOutcome = "pending" | "succeeded" | "skipped" | "failed" | "cancelled";

export interface BulkJob {
  id: string;
  action: BulkActionKey;
  action_label: string;
  params: Record<string, unknown>;
  status: BulkStatus;
  total: number;
  done: number;
  percent: number;
  counts: Record<RowOutcome, number>;
  created_by: { id: string; name: string };
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  cancel_requested: boolean;
  export_ready: boolean;
}

export interface PreviewLine {
  organisation: { id: string; name: string };
  status: "change" | "no_change" | "skipped";
  reason: string;
  message: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}

export interface BulkPreview {
  total: number;
  counts: { change: number; no_change: number; skipped: number };
  lines: PreviewLine[];
}

export interface BulkRow {
  organisation: { id: string; name: string };
  outcome: RowOutcome;
  reason: string;
  message: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  processed_at: string | null;
}

export interface BulkRowPage {
  count: number;
  page: number;
  pages: number;
  results: BulkRow[];
}

export interface ApiRefusal {
  code?: string;
  detail?: string;
}

export const bulkApi = {
  create: (body: {
    practice: string;
    action: BulkActionKey;
    params: Record<string, unknown>;
    selection: unknown;
  }): Promise<ApiResult<{ job: BulkJob; preview: BulkPreview } | ApiRefusal>> =>
    apiRequest(BULK_URL, { method: "POST", body }),
  get: (id: string): Promise<ApiResult<BulkJob>> => apiRequest<BulkJob>(`${BULK_URL}/${id}`),
  confirm: (id: string): Promise<ApiResult<BulkJob | ApiRefusal>> =>
    apiRequest(`${BULK_URL}/${id}/confirm`, { method: "POST" }),
  cancel: (id: string): Promise<ApiResult<BulkJob>> =>
    apiRequest<BulkJob>(`${BULK_URL}/${id}/cancel`, { method: "POST" }),
  rows: (id: string, outcome = "", page = 1): Promise<ApiResult<BulkRowPage>> =>
    apiRequest<BulkRowPage>(
      `${BULK_URL}/${id}/rows?page=${page}${outcome ? `&outcome=${outcome}` : ""}`,
    ),
};

export const resultsCsvUrl = (id: string) => `${BULK_URL}/${id}/results.csv`;
export const exportUrl = (id: string) => `${BULK_URL}/${id}/export`;

/** One before/after value as text: lists joined, settings spelled out. */
export function valueText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.length ? value.map(valueText).join(", ") : "—";
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => `${key}: ${valueText(item)}`)
      .join(" · ");
  }
  return String(value);
}

/** The before/after of a line, one entry per field that the action touches. */
export function diffText(
  before: Record<string, unknown>,
  after: Record<string, unknown>,
): { field: string; before: string; after: string }[] {
  return Object.keys(after).map((field) => ({
    field,
    before: valueText(before[field]),
    after: valueText(after[field]),
  }));
}
