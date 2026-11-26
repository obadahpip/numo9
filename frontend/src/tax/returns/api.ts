/** GST/HST returns API client (G-03-T10): `/api/v1/o/<org>/tax/returns…`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export type ReturnStatus = "draft" | "reviewed" | "filed" | "amended";
export type ReturnMethod = "regular" | "quick";

/** The lines a person types on the return (instalments, rebates, other debits, adjustments). */
export const ENTRY_LINES = ["104", "107", "110", "111", "113B"] as const;

export interface ReturnLine {
  line: string;
  label: string;
  amount: string;
  /** The line drills to the documents behind it. */
  drill: boolean;
  /** The line is typed on the return. */
  entry: boolean;
}

export interface ReturnPeriod {
  id: string;
  start: string;
  end: string;
  label: string;
  status: string;
  due_date: string;
  locked: boolean;
}

export interface ReturnPerson {
  id: string;
  name: string;
}

export interface ReturnVersion {
  id: string;
  version: number;
  status: ReturnStatus;
  current: boolean;
  filed_on: string | null;
  confirmation_no: string;
  amend_reason: string;
}

export interface LineChange {
  line: string;
  was: string;
  now: string;
}

export interface TaxReturn {
  id: string;
  registration: string;
  period: ReturnPeriod;
  version: number;
  status: ReturnStatus;
  method: ReturnMethod;
  is_current: boolean;
  lines: ReturnLine[];
  entries: Record<string, string>;
  prepared_by: ReturnPerson | null;
  prepared_at: string | null;
  reviewed_by: ReturnPerson | null;
  filed_by: ReturnPerson | null;
  filed_on: string | null;
  confirmation_no: string;
  amend_reason: string;
  /** Detail only: every version of the period's return, newest first. */
  versions?: ReturnVersion[];
  /** Detail only, drafts: the lines the books now put differently. */
  changed?: LineChange[];
}

/** A document behind a line, with its share of the line. */
export interface DrillDocument {
  entry: string;
  number: string;
  journal?: string;
  contact?: string;
  date: string;
  type?: string;
  url?: string;
  amount: string;
  detail?: { filed_period?: string };
}

export interface ReturnRefusal {
  code?: string;
  detail?: string;
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/tax/returns`;
const one = (org: string, id: string) => `${base(org)}/${encodeURIComponent(id)}`;

type Result<T> = Promise<ApiResult<T & ReturnRefusal>>;

export const returnsApi = {
  list: (org: string, registration?: string): Result<{ returns: TaxReturn[] }> =>
    apiRequest(
      registration ? `${base(org)}?registration=${encodeURIComponent(registration)}` : base(org),
    ),
  generate: (org: string, period: string, method?: ReturnMethod): Result<TaxReturn> =>
    apiRequest(base(org), { method: "POST", body: method ? { period, method } : { period } }),
  get: (org: string, id: string): Result<TaxReturn> => apiRequest(one(org, id)),
  recalculate: (org: string, id: string, entries?: Record<string, string>): Result<TaxReturn> =>
    apiRequest(`${one(org, id)}/recalculate`, {
      method: "POST",
      body: entries ? { entries } : {},
    }),
  review: (org: string, id: string): Result<TaxReturn> =>
    apiRequest(`${one(org, id)}/review`, { method: "POST", body: {} }),
  sendBack: (org: string, id: string, reason: string): Result<TaxReturn> =>
    apiRequest(`${one(org, id)}/send-back`, { method: "POST", body: { reason } }),
  file: (
    org: string,
    id: string,
    body: { confirmation_no: string; filed_on?: string },
  ): Result<TaxReturn> => apiRequest(`${one(org, id)}/file`, { method: "POST", body }),
  amend: (org: string, id: string, reason: string): Result<TaxReturn> =>
    apiRequest(`${one(org, id)}/amend`, { method: "POST", body: { reason } }),
  drill: (
    org: string,
    id: string,
    line: string,
  ): Result<{ line: string; documents: DrillDocument[] }> =>
    apiRequest(`${one(org, id)}/drill?line=${encodeURIComponent(line)}`),
  pdfUrl: (org: string, id: string) => `${one(org, id)}/pdf`,
  csvUrl: (org: string, id: string) => `${one(org, id)}/csv`,
};

/** The step a return is at on the stepper: prepare → review → file. */
export const STEPS = ["draft", "reviewed", "filed"] as const;

export function stepIndex(status: ReturnStatus): number {
  if (status === "amended") return 2;
  return STEPS.indexOf(status);
}

/** The worksheet url of a return. */
export const returnUrl = (org: string, id: string) =>
  `/o/${encodeURIComponent(org)}/tax/returns/${encodeURIComponent(id)}`;
