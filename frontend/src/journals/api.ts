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
}

export const journalsUrl = (org: string, suffix = "") =>
  `/api/v1/o/${encodeURIComponent(org)}/journals${suffix}`;

export const getJournal = (org: string, id: string): Promise<ApiResult<Journal>> =>
  apiRequest<Journal>(journalsUrl(org, `/${encodeURIComponent(id)}`));
