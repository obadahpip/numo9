/**
 * Manual journals write API client (C-03-T10): `POST journals`, `POST journals/check`,
 * `POST journals/<id>/post` under `/api/v1/o/<org>/`.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

import { journalsUrl, type Book, type Journal } from "../api";

/** The journal types a person chooses (C-03-T01); system types never reach the picker. */
export const SELECTABLE_TYPES = ["general", "adjusting", "reclass", "tax_adjustment"] as const;
export type JournalTypeKey = (typeof SELECTABLE_TYPES)[number];

export interface LineInput {
  account: string;
  debit: string;
  credit: string;
  book: Book;
  contact: string | null;
  description: string;
}

export interface JournalInput {
  date: string;
  journal_type: JournalTypeKey;
  narration: string;
  auto_reverse_on: string | null;
  lines: LineInput[];
  attachments: string[];
  override_reason?: string;
  post?: boolean;
}

export interface Problem {
  code: string;
  message: string;
}

export interface Shortfall {
  account: { id: string; label: string };
  change: string;
  at_date: string;
  date: string;
  at_today: string;
  today: string;
  lowest: string;
  lowest_on: string;
  message: string;
}

export interface CheckResult {
  ok: boolean;
  errors: Problem[];
  shortfalls: Shortfall[];
  adviser: boolean;
  needs: { attachment: boolean; contact_lines: number[] };
}

export interface Refusal {
  code?: string;
  detail?: string;
  errors?: Problem[];
  adviser?: boolean;
  shortfalls?: Shortfall[];
}

export const writeApi = {
  check: (org: string, body: JournalInput): Promise<ApiResult<CheckResult>> =>
    apiRequest<CheckResult>(journalsUrl(org, "/check"), { method: "POST", body }),
  create: (org: string, body: JournalInput): Promise<ApiResult<Journal & Refusal>> =>
    apiRequest<Journal & Refusal>(journalsUrl(org), { method: "POST", body }),
  /** C-04-T07 workflow actions on an existing journal. */
  action: (
    org: string,
    id: string,
    action: "post" | "submit" | "approve" | "reject" | "withdraw" | "reverse",
    body: Record<string, unknown> = {},
  ): Promise<ApiResult<Journal & Refusal>> =>
    apiRequest<Journal & Refusal>(journalsUrl(org, `/${encodeURIComponent(id)}/${action}`), {
      method: "POST",
      body,
    }),
};

/** Lines with an account and an amount: what the server is asked about. */
export function filledLines(lines: LineInput[]): LineInput[] {
  return lines.filter(
    (line) => line.account && (Number(line.debit) > 0 || Number(line.credit) > 0),
  );
}
