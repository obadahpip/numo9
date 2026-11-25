/**
 * Find & recode API client (C-07-T09): `/api/v1/o/<org>/recode/` — search, preview, execute,
 * batches, undo, report.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export type Match = "all" | "any";

export interface Condition {
  field: string;
  op: string;
  value: unknown;
}

export interface Criteria {
  match: Match;
  conditions: Condition[];
}

export interface Coding {
  account: string;
  tax_code: string;
  tracking: Record<string, string>;
  contact: string | null;
}

export interface LineKey {
  entry: string;
  line_no: number;
  fingerprint?: string;
}

export interface FoundLine {
  entry: string;
  number: string;
  date: string;
  type: string;
  narration: string;
  line_no: number;
  book: "both" | "accounting" | "tax";
  account: { id: string; label: string };
  debit: string;
  credit: string;
  tax_code: string;
  contact: { id: string; label: string } | null;
  tracking: Record<string, string>;
  description: string;
  fingerprint: string;
}

export interface Reason {
  code: string;
  message: string;
  detail?: Record<string, unknown>;
}

export interface ExcludedLine extends FoundLine {
  reason: Reason;
}

export interface SearchResult {
  count: number;
  page: number;
  page_size: number;
  lines: FoundLine[];
  keys: LineKey[];
  excluded_count: number;
  excluded: ExcludedLine[];
}

export interface Changes {
  account?: string;
  tax_code?: string;
  tracking?: Record<string, string | null>;
  contact?: string | null;
}

export interface PreviewLine {
  entry: string;
  number: string;
  date: string;
  line_no: number;
  book: string;
  debit: string;
  credit: string;
  before: Coding;
  after: Coding;
  changed: ("account" | "tax_code" | "tracking" | "contact")[];
  fingerprint: string;
}

export interface TaxImpact {
  entry: string;
  number: number;
  line_no: number;
  base: string;
  from: string;
  to: string;
  before: Record<string, string>;
  after: Record<string, string>;
  delta: string;
}

export interface PreviewSummary {
  lines: number;
  accounts: number;
  excluded: number;
  unchanged: number;
  totals_unchanged: boolean;
  tax_delta: string;
  needs_confirmation: boolean;
}

type Totals = Record<string, { debit: string; credit: string }>;

export interface PreviewResult {
  summary: PreviewSummary;
  count: number;
  page: number;
  page_size: number;
  lines: PreviewLine[];
  excluded: ExcludedLine[];
  totals_before: Totals;
  totals_after: Totals;
  accounts: Record<string, { before: string; after: string }>;
  tax_impact: TaxImpact[];
}

export type BatchStatus = "draft" | "running" | "completed" | "failed" | "undone";

export interface Problem {
  entry: string;
  number: string;
  lines: number[];
  code: string;
  message: string;
}

export interface Blocker {
  entry: string | null;
  number: string | null;
  date?: string;
  code: string;
  message: string;
  detail?: Record<string, unknown>;
}

export interface Batch {
  id: string;
  name: string;
  label: string;
  status: BatchStatus;
  criteria: Criteria;
  changes: Changes;
  line_count: number;
  excluded_count: number;
  progress: number;
  problem_count: number;
  created_at: string;
  executed_by: { id: string; name: string } | null;
  executed_at: string | null;
  undone_by: { id: string; name: string } | null;
  undone_at: string | null;
  undo_reason: string;
  job: string | null;
  error: string;
  problems?: Problem[];
  undo?: { allowed: boolean; blocked: Blocker[] };
}

export interface Refusal {
  code?: string;
  detail?: string;
  field?: string;
  blocked?: Blocker[];
}

export type ReportFormat = "csv" | "xlsx" | "pdf";

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/recode`;
type Result<T> = Promise<ApiResult<T & Refusal>>;

export const recodeApi = {
  search: (org: string, criteria: Criteria, page = 1, pageSize = 50): Result<SearchResult> =>
    apiRequest(`${base(org)}/search`, {
      method: "POST",
      body: { criteria, page, page_size: pageSize },
    }),
  preview: (
    org: string,
    criteria: Criteria,
    changes: Changes,
    selection: LineKey[] | null,
    page = 1,
  ): Result<PreviewResult> =>
    apiRequest(`${base(org)}/preview`, {
      method: "POST",
      body: { criteria, changes, selection, page, page_size: 100 },
    }),
  execute: (
    org: string,
    body: {
      criteria: Criteria;
      changes: Changes;
      selection: LineKey[] | null;
      name?: string;
      confirm_tax?: boolean;
    },
  ): Result<Batch> => apiRequest(`${base(org)}/execute`, { method: "POST", body }),
  batches: (org: string): Result<{ batches: Batch[] }> => apiRequest(`${base(org)}/batches`),
  batch: (org: string, id: string): Result<Batch> =>
    apiRequest(`${base(org)}/batches/${encodeURIComponent(id)}`),
  undo: (org: string, id: string, reason: string): Result<Batch> =>
    apiRequest(`${base(org)}/batches/${encodeURIComponent(id)}/undo`, {
      method: "POST",
      body: { reason },
    }),
  reportUrl: (org: string, id: string, format: ReportFormat) =>
    `${base(org)}/batches/${encodeURIComponent(id)}/report?export=${format}`,
};
