/** Recurring journals API client (C-04-T07): `/api/v1/o/<org>/journals/recurring…`. */
import { apiRequest, type ApiResult } from "@/auth/client";

import { journalsUrl } from "../api";
import type { JournalTypeKey } from "../write/api";

export interface RecurringLine {
  account: string;
  debit: string;
  credit: string;
  book?: string;
  contact?: string | null;
  description?: string;
}

export interface RecurringTemplate {
  id: string;
  name: string;
  narration: string;
  journal_type: JournalTypeKey;
  lines: RecurringLine[];
  rrule: string;
  start_date: string;
  end_date: string | null;
  mode: "draft" | "post";
  next_run: string | null;
  paused: boolean;
  version: number;
  created_by: string;
  runs?: {
    date: string;
    status: "created" | "skipped";
    code: string;
    message: string;
    journal: { id: string; status: string } | null;
  }[];
}

export type RecurringInput = Omit<
  RecurringTemplate,
  "id" | "next_run" | "version" | "created_by" | "runs"
>;

export interface RecurringRefusal {
  code?: string;
  detail?: string;
  [field: string]: unknown;
}

export const recurringApi = {
  list: (org: string): Promise<ApiResult<{ results: RecurringTemplate[] }>> =>
    apiRequest(journalsUrl(org, "/recurring")),
  get: (org: string, id: string): Promise<ApiResult<RecurringTemplate>> =>
    apiRequest(journalsUrl(org, `/recurring/${encodeURIComponent(id)}`)),
  create: (
    org: string,
    body: RecurringInput,
  ): Promise<ApiResult<RecurringTemplate & RecurringRefusal>> =>
    apiRequest(journalsUrl(org, "/recurring"), { method: "POST", body }),
  update: (
    org: string,
    id: string,
    body: Partial<RecurringInput>,
  ): Promise<ApiResult<RecurringTemplate & RecurringRefusal>> =>
    apiRequest(journalsUrl(org, `/recurring/${encodeURIComponent(id)}`), {
      method: "PATCH",
      body,
    }),
  /** The next dates of an unsaved schedule — the same generator as the tick (C-04-T05). */
  preview: (
    org: string,
    body: { rrule: string; start_date: string; end_date: string | null; count: number },
  ): Promise<ApiResult<{ dates: string[] } & RecurringRefusal>> =>
    apiRequest(journalsUrl(org, "/recurring/preview"), { method: "POST", body }),
};

/** The schedule builder's choices and the RFC 5545 rule they make. */
export type Frequency = "weekly" | "monthly" | "quarterly" | "yearly";

export function buildRule(frequency: Frequency, every: number): string {
  const n = Math.max(1, Math.floor(every) || 1);
  switch (frequency) {
    case "weekly":
      return `FREQ=WEEKLY;INTERVAL=${n}`;
    case "quarterly":
      return `FREQ=MONTHLY;INTERVAL=${3 * n}`;
    case "yearly":
      return `FREQ=YEARLY;INTERVAL=${n}`;
    default:
      return `FREQ=MONTHLY;INTERVAL=${n}`;
  }
}

/** The builder's choices back from a rule it made (other rules: monthly, every 1). */
export function readRule(rule: string): { frequency: Frequency; every: number } {
  const parts = Object.fromEntries(
    rule
      .replace(/^RRULE:/i, "")
      .split(";")
      .map((part) => part.split("=") as [string, string]),
  );
  const interval = Number(parts.INTERVAL ?? 1) || 1;
  if (parts.FREQ === "WEEKLY") return { frequency: "weekly", every: interval };
  if (parts.FREQ === "YEARLY") return { frequency: "yearly", every: interval };
  if (parts.FREQ === "MONTHLY" && interval % 3 === 0)
    return { frequency: "quarterly", every: interval / 3 };
  return { frequency: "monthly", every: interval };
}
