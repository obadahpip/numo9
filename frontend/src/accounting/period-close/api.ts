/**
 * Period close API client (C-06-T07): `/api/v1/o/<org>/period-close/` — the module × month
 * timeline, the checklist of a month, close, year-end, reopen.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export type MonthStatus = "closed" | "locked" | "open";

export interface CloseRecord {
  id: string;
  module: string;
  period_end: string;
  kind: "month" | "year_end";
  closed_by: { id: string; name: string } | null;
  closed_at: string;
  reopened_by: { id: string; name: string } | null;
  reopened_at: string | null;
  reason: string;
  entries: { book: "accounting" | "tax"; id: string; number: number | null }[];
}

export interface TimelineMonth {
  start: string;
  end: string;
  status: MonthStatus;
  close: string | null;
  past: boolean;
}

export interface Timeline {
  fiscal_year: { start: string; end: string };
  today: string;
  modules: { module: string; label: string; months: TimelineMonth[] }[];
  closes: CloseRecord[];
  year_end: CloseRecord | null;
  is_adviser: boolean;
}

export interface ChecklistItem {
  key: "drafts" | "awaiting_approval" | "unfiled_tax" | "exceptions";
  label: string;
  count: number;
  detail: Record<string, unknown>;
  link: string;
}

export interface Refusal {
  code?: string;
  detail?: string;
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/period-close`;
type Result<T> = Promise<ApiResult<T & Refusal>>;

export const periodCloseApi = {
  timeline: (org: string, year?: number): Result<Timeline> =>
    apiRequest(`${base(org)}/${year ? `?year=${year}` : ""}`),
  checklist: (
    org: string,
    periodEnd: string,
  ): Result<{ period_end: string; items: ChecklistItem[] }> =>
    apiRequest(`${base(org)}/checklist?period_end=${encodeURIComponent(periodEnd)}`),
  close: (org: string, module: string, periodEnd: string): Result<CloseRecord> =>
    apiRequest(`${base(org)}/close`, { method: "POST", body: { module, period_end: periodEnd } }),
  yearEnd: (org: string, fiscalYearEnd: string): Result<CloseRecord> =>
    apiRequest(`${base(org)}/year-end`, {
      method: "POST",
      body: { fiscal_year_end: fiscalYearEnd },
    }),
  reopen: (org: string, id: string, reason: string, force = false): Result<CloseRecord> =>
    apiRequest(`${base(org)}/${encodeURIComponent(id)}/reopen`, {
      method: "POST",
      body: { reason, force },
    }),
};
