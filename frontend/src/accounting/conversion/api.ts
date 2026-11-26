/**
 * Conversion balances API client (C-05-T09): `/api/v1/o/<org>/conversion/` — the session and the
 * wizard's saved progress, the opening lines, the open invoices and bills, the difference,
 * finalise, the trial balance import and the correcting journals.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export const STEPS = ["date", "bank", "invoices", "bills", "other", "review"] as const;
export type StepKey = (typeof STEPS)[number];

export interface Person {
  id: string;
  name: string;
}

export interface EntryRef {
  id: string;
  number: number | null;
  date: string;
  url: string;
}

export interface Correction {
  id: string;
  reason: string;
  entry: EntryRef | null;
  created_by: Person | null;
  created_at: string;
}

export interface Session {
  id: string;
  conversion_date: string;
  status: "draft" | "finalised";
  lock_balances: boolean;
  step: StepKey;
  completed_steps: StepKey[];
  finalised_by: Person | null;
  finalised_at: string | null;
  opening_entry: EntryRef | null;
  corrections: Correction[];
}

export interface Reason {
  code: string;
  message: string;
}

export interface ControlCheck {
  role: "ar" | "ap";
  label: string;
  account: { id: string; code: string; name: string } | null;
  control: string;
  documents: string;
  count: number;
  gap: string;
  matches: boolean;
}

export interface Difference {
  debits: string;
  credits: string;
  difference: string;
  balanced: boolean;
  lines: number;
  controls: ControlCheck[];
  accounts: ControlCheck[];
  warnings: Reason[];
  opening_equity_missing: boolean;
  reasons: Reason[];
  can_finalise: boolean;
}

export interface Overview {
  session: Session | null;
  difference: Difference | null;
  steps: { key: StepKey; label: string }[];
  is_adviser: boolean;
}

export interface LineAccount {
  id: string;
  code: string;
  name: string;
  type: string;
  subtype: string;
  system_role: string;
  is_bank: boolean;
  require_contact: boolean;
}

export interface Line {
  id: string;
  account: LineAccount;
  debit: string;
  credit: string;
  description: string;
  contact: { id: string; name: string } | null;
}

export interface LineInput {
  account: string;
  debit: string;
  credit: string;
  description?: string;
  contact?: string | null;
}

export type DocumentKind = "invoice" | "bill";

export interface OpeningDocument {
  id: string;
  kind: DocumentKind;
  document_id: string;
  number: string;
  supplier_invoice_no: string;
  contact: { id: string; name: string } | null;
  date: string;
  due_date: string | null;
  reference: string;
  total: string;
  outstanding: string;
  amount_due: string;
  status: string;
}

/** A row of the open documents grid as sent: contact by name or id (pasted). */
export interface DocumentInput {
  contact: string;
  number?: string;
  supplier_invoice_no?: string;
  date: string;
  due_date?: string;
  total: string;
  outstanding?: string;
  reference?: string;
}

export interface RowProblem {
  field: string;
  code: string;
  message: string;
}

export interface RowResult {
  row: number;
  ok: boolean;
  errors: RowProblem[];
  id: string | null;
}

export interface DocumentsReport {
  dry_run: boolean;
  rows: RowResult[];
  ok: number;
  errors: number;
  written: number;
  documents?: OpeningDocument[];
  difference?: Difference;
}

export interface Refusal {
  code?: string;
  detail?: string;
  params?: Record<string, string>;
  rows?: ({ row: number } & RowProblem)[] | RowResult[];
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/conversion/`;
type Result<T> = Promise<ApiResult<T & Refusal>>;

export const conversionApi = {
  overview: (org: string): Result<Overview> => apiRequest(base(org)),
  start: (org: string, conversionDate: string): Result<Overview> =>
    apiRequest(base(org), { method: "POST", body: { conversion_date: conversionDate } }),
  save: (
    org: string,
    changes: Partial<{
      conversion_date: string;
      lock_balances: boolean;
      step: StepKey;
      completed_steps: StepKey[];
    }>,
  ): Result<Overview> => apiRequest(base(org), { method: "PATCH", body: changes }),
  lines: (org: string): Result<{ lines: Line[] }> => apiRequest(`${base(org)}lines`),
  setLines: (org: string, lines: LineInput[]): Result<{ lines: Line[]; difference: Difference }> =>
    apiRequest(`${base(org)}lines`, { method: "PUT", body: { lines } }),
  documents: (org: string, kind: DocumentKind): Result<{ documents: OpeningDocument[] }> =>
    apiRequest(`${base(org)}documents?kind=${kind}`),
  addDocuments: (
    org: string,
    kind: DocumentKind,
    rows: DocumentInput[],
    dryRun = false,
  ): Result<DocumentsReport> =>
    apiRequest(`${base(org)}documents`, {
      method: "POST",
      body: { kind, rows, dry_run: dryRun },
    }),
  removeDocuments: (
    org: string,
    ids: string[],
  ): Result<{ removed: number; documents: OpeningDocument[]; difference: Difference }> =>
    apiRequest(`${base(org)}documents/remove`, { method: "POST", body: { ids } }),
  difference: (org: string): Result<{ difference: Difference | null }> =>
    apiRequest(`${base(org)}difference`),
  finalise: (org: string, lockBalances: boolean): Result<Overview> =>
    apiRequest(`${base(org)}finalise`, {
      method: "POST",
      body: { lock_balances: lockBalances },
    }),
};
