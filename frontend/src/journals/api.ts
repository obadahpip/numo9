/** Journals read API client (C-02-T15): `/api/v1/o/<org>/journals…`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export type Book = "both" | "accounting" | "tax";
export type JournalStatus = "draft" | "awaiting_approval" | "posted" | "reversed";

export interface JournalLink {
  id: string;
  number: string;
}

export interface JournalLine {
  line: number;
  account: { id: string; code: string; name: string };
  debit: string;
  credit: string;
  book: Book;
  contact: { id: string; name: string } | null;
  description: string;
  tax_code: string;
  tracking: Record<string, unknown>;
}

export interface Journal {
  id: string;
  number: string;
  date: string;
  type: string;
  status: JournalStatus;
  narration: string;
  source: { type: string; id: string } | null;
  book_scope: Book;
  total: string;
  lines: JournalLine[];
  books: Partial<Record<"accounting" | "tax", { debit: string; credit: string }>>;
  reversal_of: JournalLink | null;
  reversed_by: JournalLink | null;
  posted_by: { id: string; name: string } | null;
  posted_at: string | null;
  audit: { action: string; by: string; at: string }[];
  journal_type?: string;
  created_by?: { id: string; name: string } | null;
  /** The latest approval round (C-04). */
  approval?: {
    decision: "pending" | "approved" | "rejected" | "withdrawn";
    submitted_by: { id: string; name: string } | null;
    submitted_at: string | null;
    decided_by: { id: string; name: string } | null;
    decided_at: string | null;
    reason: string;
  } | null;
  /** What the signed-in person may do with it (C-04-T10). */
  viewer?: { is_author: boolean; can_approve: boolean; blocked: string | null };
}

export const journalsUrl = (org: string, suffix = "") =>
  `/api/v1/o/${encodeURIComponent(org)}/journals${suffix}`;

export const getJournal = (org: string, id: string): Promise<ApiResult<Journal>> =>
  apiRequest<Journal>(journalsUrl(org, `/${encodeURIComponent(id)}`));

/** One row of the journals list (`GET journals?status=`, C-02-T15). */
export interface JournalSummary {
  id: string;
  number: string;
  date: string;
  type: string;
  journal_type: string;
  journal_type_label: string;
  status: JournalStatus;
  narration: string;
  total: string;
  lines: number;
}

export interface JournalPage {
  results: JournalSummary[];
  count: number;
  next_offset: number | null;
}

/** The journals list's tabs (K-09-T22; Phase 1 journals list: All / Draft / Awaiting / Posted / Reversed). */
export const JOURNAL_TABS = ["all", "draft", "awaiting_approval", "posted", "reversed"] as const;
export type JournalTab = (typeof JOURNAL_TABS)[number];

export const isJournalTab = (value: unknown): value is JournalTab =>
  typeof value === "string" && (JOURNAL_TABS as readonly string[]).includes(value);

/** The `status` query of a tab: "all" asks for every status (the API alone answers posted and reversed). */
export function tabStatuses(tab: JournalTab): string {
  return tab === "all" ? "draft,awaiting_approval,posted,reversed" : tab;
}

export const listJournals = (
  org: string,
  tab: JournalTab,
  { q = "", offset = 0 }: { q?: string; offset?: number } = {},
): Promise<ApiResult<JournalPage>> => {
  const params = new URLSearchParams({ status: tabStatuses(tab), limit: "50" });
  if (q.trim()) params.set("q", q.trim());
  if (offset) params.set("offset", String(offset));
  return apiRequest<JournalPage>(journalsUrl(org, `?${params.toString()}`));
};
