/** Filing cycles API client (G-03a-T16): `/api/v1/o/<org>/tax/registrations/<id>/…`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export type Frequency = "monthly" | "quarterly" | "annual";
export type PeriodKind = "regular" | "custom" | "stub";
export type PeriodStatus = "open" | "closed" | "filed" | "paid";
export type Attention = "" | "due_soon" | "overdue";

export interface FilingPeriod {
  id: string;
  start: string;
  end: string;
  kind: PeriodKind;
  frequency: Frequency | "";
  sequence_no: number;
  due_date: string;
  payment_due_date: string;
  status: PeriodStatus;
  note: string;
  attention?: Attention;
  /** The return due date was moved to the next business day (weekend or holiday). */
  due_rolled?: boolean;
  instalments?: { quarter_start: string; quarter_end: string; due_date: string }[];
}

export interface FilingCycle {
  id: string;
  frequency: Frequency;
  effective_from: string;
  approval_ref: string;
  approval_date: string | null;
  note: string;
  created_by: string;
  created_at: string;
}

export interface FilingRegistration {
  id: string;
  type: string;
  number: string;
  start_date: string | null;
  stop_date: string | null;
}

export interface PeriodsResponse {
  registration: FilingRegistration;
  today: string;
  results: FilingPeriod[];
}

export interface FilingWarning {
  code: string;
  message: string;
}

export interface FilingDiff {
  removed: FilingPeriod[];
  added: FilingPeriod[];
  changed: { before: FilingPeriod; after: FilingPeriod }[];
  periods: FilingPeriod[];
  warnings: FilingWarning[];
}

export interface FilingRefusal {
  code?: string;
  detail?: string;
}

export interface SwitchChange {
  frequency: Frequency;
  effective_from: string;
  approval_ref?: string;
  approval_date?: string | null;
  note?: string;
}

export interface CustomChange {
  start: string;
  end: string;
  note?: string;
}

export type PreviewChange =
  | ({ action: "switch" } & SwitchChange)
  | ({ action: "custom" } & CustomChange)
  | { action: "delete_custom"; period: string };

const base = (org: string, registration: string) =>
  `/api/v1/o/${encodeURIComponent(org)}/tax/registrations/${encodeURIComponent(registration)}`;

type Result<T> = Promise<ApiResult<T & FilingRefusal>>;

export const filingApi = {
  periods: (org: string, registration: string): Result<PeriodsResponse> =>
    apiRequest(`${base(org, registration)}/periods`),
  cycles: (org: string, registration: string): Result<{ results: FilingCycle[] }> =>
    apiRequest(`${base(org, registration)}/cycles`),
  preview: (org: string, registration: string, body: PreviewChange): Result<FilingDiff> =>
    apiRequest(`${base(org, registration)}/preview`, { method: "POST", body }),
  switchFrequency: (org: string, registration: string, body: SwitchChange): Result<FilingDiff> =>
    apiRequest(`${base(org, registration)}/cycles`, { method: "POST", body }),
  addCustom: (org: string, registration: string, body: CustomChange): Result<FilingDiff> =>
    apiRequest(`${base(org, registration)}/custom-periods`, { method: "POST", body }),
  removeCustom: (org: string, registration: string, period: string): Result<FilingDiff> =>
    apiRequest(`${base(org, registration)}/custom-periods/${encodeURIComponent(period)}`, {
      method: "DELETE",
    }),
};

/** The colour key of a period block: what it needs first, else its status. */
export type BlockState = "filed" | "overdue" | "due_soon" | "open";

export function blockState(period: FilingPeriod): BlockState {
  if (period.status === "filed" || period.status === "paid") return "filed";
  if (period.attention === "overdue") return "overdue";
  if (period.attention === "due_soon") return "due_soon";
  return "open";
}

const DAY = 86_400_000;
const at = (day: string) => Date.parse(`${day}T00:00:00Z`);

/** Days from `start` to `end`, both included. */
export function daysIn(start: string, end: string): number {
  return Math.round((at(end) - at(start)) / DAY) + 1;
}

/** The day after an ISO date. */
export function nextDay(day: string): string {
  return new Date(at(day) + DAY).toISOString().slice(0, 10);
}
