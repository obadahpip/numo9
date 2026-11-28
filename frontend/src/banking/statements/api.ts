/**
 * Statement import API client (F-02-T11): `/api/v1/o/<org>/bank-accounts/<id>/imports…` — upload,
 * preview (dry run), commit, undo and history — and the account's statement lines (F-02-T13).
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export type Role =
  | "date"
  | "description"
  | "payee"
  | "reference"
  | "fitid"
  | "amount"
  | "debit"
  | "credit"
  | "balance"
  | "ignore";
export type Sign = "signed" | "inverted" | "debit_credit";
export type LineStatus = "new" | "duplicate" | "error";
export type ImportStatus = "pending" | "processing" | "committed" | "undone" | "failed";

export interface Layout {
  columns: Role[];
  date_format: string;
  sign: Sign;
  has_header: boolean;
  skip_rows: number;
  decimal_separator: "." | ",";
}

export interface Counts {
  total: number;
  new: number;
  duplicate: number;
  error: number;
}

export interface StatementImport {
  id: string;
  bank_account: string;
  file_name: string;
  file_format: string;
  source: string;
  status: ImportStatus;
  status_label: string;
  mapping: { id: string; name: string } | null;
  counts: Counts;
  created_at: string;
  created_by: { name: string } | null;
  committed_at: string | null;
  undone_at: string | null;
  in_use?: number;
  can_undo?: boolean;
}

export interface SavedMapping {
  id: string;
  name: string;
  institution: string;
  builtin: boolean;
  layout: Layout;
  score?: number;
}

export interface SampleRow {
  row: number;
  cells: string[];
}

export interface Upload {
  import: StatementImport;
  format: string;
  encoding: string;
  delimiter: string;
  warnings: string[];
  tabular: boolean;
  lines: number;
  sample?: { rows: SampleRow[]; width: number };
  layout?: Layout | null;
  mapping?: SavedMapping | null;
  mappings?: SavedMapping[];
  date_formats?: string[];
  date_ambiguous?: boolean;
  choices?: { roles: Role[]; signs: Sign[]; date_formats: string[] };
}

export interface Reason {
  code: string;
  message: string;
}

export interface PreviewLine {
  row: number;
  date: string | null;
  amount: string | null;
  description: string;
  payee: string;
  reference: string;
  fitid: string;
  status: LineStatus;
  reasons: Reason[];
}

export interface Balance {
  amount: string;
  date: string | null;
}

export interface Preview {
  import: StatementImport;
  counts: Counts;
  balances: { opening: Balance | null; closing: Balance | null };
  warnings: string[];
  layout: Layout | null;
  count: number;
  results: PreviewLine[];
}

export interface ImportRefusal {
  code?: string;
  detail?: string;
  count?: number;
  lines?: { id: string; date: string; amount: string; description: string; status: string }[];
  file?: string[];
}

export interface LayoutChoice {
  mapping?: string | null;
  layout?: Layout | null;
}

const base = (org: string, account: string) =>
  `/api/v1/o/${encodeURIComponent(org)}/bank-accounts/${encodeURIComponent(account)}`;

export const importsApi = {
  history: (
    org: string,
    account: string,
  ): Promise<ApiResult<{ results: StatementImport[] } & ImportRefusal>> =>
    apiRequest(`${base(org, account)}/imports`),
  upload: (
    org: string,
    account: string,
    file: File,
  ): Promise<ApiResult<Upload & ImportRefusal>> => {
    const form = new FormData();
    form.append("file", file);
    return apiRequest(`${base(org, account)}/imports`, { method: "POST", body: form });
  },
  get: (org: string, account: string, id: string): Promise<ApiResult<Upload & ImportRefusal>> =>
    apiRequest(`${base(org, account)}/imports/${id}`),
  preview: (
    org: string,
    account: string,
    id: string,
    choice: LayoutChoice & { status?: LineStatus | null; limit?: number },
  ): Promise<ApiResult<Preview & ImportRefusal>> =>
    apiRequest(`${base(org, account)}/imports/${id}/preview`, { method: "POST", body: choice }),
  commit: (
    org: string,
    account: string,
    id: string,
    choice: LayoutChoice & { skip_errors: boolean },
  ): Promise<ApiResult<{ import: StatementImport; job?: { id: string } } & ImportRefusal>> =>
    apiRequest(`${base(org, account)}/imports/${id}/commit`, { method: "POST", body: choice }),
  undo: (
    org: string,
    account: string,
    id: string,
  ): Promise<ApiResult<{ import: StatementImport } & ImportRefusal>> =>
    apiRequest(`${base(org, account)}/imports/${id}/undo`, { method: "POST", body: {} }),
};

/** The API's message for a refusal (a file problem, a layout problem…), or null. */
export function refusalText(body: ImportRefusal | null | undefined): string | null {
  if (!body) return null;
  if (body.detail) return body.detail;
  if (Array.isArray(body.file) && body.file[0]) return body.file[0];
  return null;
}

/** The rows the mapping grid shows: the header row (if any) and the first `count` data rows. */
export function gridRows(
  rows: SampleRow[],
  layout: Pick<Layout, "has_header" | "skip_rows">,
  count = 5,
): { header: SampleRow | null; data: SampleRow[] } {
  const rest = rows.slice(Math.max(0, layout.skip_rows));
  const header = layout.has_header ? (rest[0] ?? null) : null;
  return {
    header,
    data: rest.slice(layout.has_header ? 1 : 0, (layout.has_header ? 1 : 0) + count),
  };
}

/** A layout is usable when it has a date column and its amount column(s). */
export function layoutComplete(layout: Layout): boolean {
  const roles = new Set(layout.columns);
  if (!roles.has("date")) return false;
  return layout.sign === "debit_credit"
    ? roles.has("debit") && roles.has("credit")
    : roles.has("amount");
}

/** `columns` padded with "ignore" to the file's width. */
export function padColumns(columns: Role[], width: number): Role[] {
  return Array.from({ length: Math.max(width, columns.length) }, (_, i) => columns[i] ?? "ignore");
}
