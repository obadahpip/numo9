/**
 * Banking API client (F-01-T07): `/api/v1/o/<org>/bank-accounts…` and `/bank-transactions…`.
 * Balances are the ledger balance of the account's ledger account (never edited); the statement
 * balance is optional and sits beside it.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export type BankAccountType =
  "chequing" | "savings" | "credit_card" | "line_of_credit" | "loan" | "cash" | "clearing";

export const BANK_ACCOUNT_TYPES: readonly BankAccountType[] = [
  "chequing",
  "savings",
  "credit_card",
  "line_of_credit",
  "loan",
  "cash",
  "clearing",
];

export interface BankAccount {
  id: string;
  type: BankAccountType;
  type_label: string;
  display_name: string;
  institution: string;
  currency: string;
  masked_number: string;
  ledger_account: { id: string; code: string; name: string };
  ledger_balance: string;
  statement_balance: string | null;
  statement_balance_date: string | null;
  is_reconciled_tracking: boolean;
  is_liability: boolean;
  archived_at: string | null;
  transaction_count: number;
  last_activity: string | null;
}

export interface NewBankAccount {
  type: BankAccountType;
  display_name: string;
  institution?: string;
  currency?: string;
  account_last4?: string;
}

export type BankAccountChanges = Partial<{
  display_name: string;
  institution: string;
  currency: string;
  account_last4: string;
  statement_balance: string | null;
  statement_balance_date: string | null;
  is_reconciled_tracking: boolean;
}>;

export type TaxMode = "exclusive" | "inclusive" | "no_tax";
export type BankTransactionKind = "spend" | "receive";

export interface TaxPortion {
  role: string;
  amount: string;
  recoverable?: boolean;
}

export interface MoneyLineInput {
  account: string;
  amount: string;
  description?: string;
  tax_code?: string;
  taxes?: TaxPortion[];
}

export interface NewBankTransaction {
  kind: BankTransactionKind;
  bank_account: string;
  date: string;
  contact?: string | null;
  reference?: string;
  tax_mode?: TaxMode;
  lines: MoneyLineInput[];
  attachments?: string[];
  override_reason?: string;
}

export interface BankTransaction {
  id: string;
  kind: BankTransactionKind;
  bank_account: { id: string; name: string };
  date: string;
  contact: { id: string; name: string } | null;
  reference: string;
  tax_mode: TaxMode;
  subtotal: string;
  tax_total: string;
  total: string;
  /** `draft`: a bank rule's coding of a statement line waiting for review (F-04-T07). */
  status: "draft" | "posted" | "voided";
  voided_at: string | null;
  journal: { id: string; number: number | null } | null;
  lines?: {
    line: number;
    account: { id: string; code: string };
    description: string;
    amount: string;
    net: string;
    tax_amount: string;
    tax_code: string;
  }[];
}

export interface Refusal {
  code?: string;
  detail?: string;
  count?: number;
  errors?: { code: string; message: string }[];
  /** F-07: the accounts a posting would take below zero (negative-balance refusals). */
  shortfalls?: { account: { id: string; label: string }; message: string; action?: string }[];
  adviser?: boolean;
}

export type AccountStatusFilter = "active" | "archived" | "all";

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}`;

export interface TransactionFilters {
  bank_account?: string;
  kind?: BankTransactionKind;
  status?: "draft" | "posted" | "voided";
  from?: string;
  to?: string;
}

/** Input of `GET bank-transactions/tax-default` (G-02-T09). */
export interface TaxDefaultQuery {
  kind: BankTransactionKind;
  date: string;
  account?: string;
  contact?: string;
  amount?: string;
  tax_mode?: TaxMode;
}

/** A line's default tax code and why: spend → account default, then the supplier's province;
 * receive → the sales place-of-supply table. `"auto"` as a line's `tax_code` posts the same. */
export interface TaxDefault {
  code: string;
  name: string;
  version: number | null;
  source: "override" | "item" | "contact" | "place_of_supply" | "account" | "none";
  explanation: string;
  params: Record<string, string>;
  province: string;
  flags: string[];
  warnings: string[];
  taxes: TaxPortion[];
}

export const AUTO_TAX_CODE = "auto";

export function taxDefaultQuery(query: TaxDefaultQuery): string {
  return new URLSearchParams(
    Object.entries(query).filter((entry): entry is [string, string] => Boolean(entry[1])),
  ).toString();
}

export const bankingApi = {
  accounts: (
    org: string,
    status: AccountStatusFilter = "active",
  ): Promise<ApiResult<{ results: BankAccount[] }>> =>
    apiRequest(`${base(org)}/bank-accounts?status=${status}`),
  account: (org: string, id: string): Promise<ApiResult<BankAccount>> =>
    apiRequest(`${base(org)}/bank-accounts/${id}`),
  create: (org: string, body: NewBankAccount): Promise<ApiResult<BankAccount & Refusal>> =>
    apiRequest(`${base(org)}/bank-accounts`, { method: "POST", body }),
  update: (
    org: string,
    id: string,
    body: BankAccountChanges,
  ): Promise<ApiResult<BankAccount & Refusal>> =>
    apiRequest(`${base(org)}/bank-accounts/${id}`, { method: "PATCH", body }),
  remove: (org: string, id: string): Promise<ApiResult<Refusal>> =>
    apiRequest(`${base(org)}/bank-accounts/${id}`, { method: "DELETE" }),
  archive: (org: string, id: string): Promise<ApiResult<BankAccount>> =>
    apiRequest(`${base(org)}/bank-accounts/${id}/archive`, { method: "POST" }),
  restore: (org: string, id: string): Promise<ApiResult<BankAccount>> =>
    apiRequest(`${base(org)}/bank-accounts/${id}/restore`, { method: "POST" }),
  transactions: (
    org: string,
    filters: TransactionFilters = {},
  ): Promise<ApiResult<{ results: BankTransaction[] }>> => {
    const params = new URLSearchParams(
      Object.entries(filters).filter((entry): entry is [string, string] => Boolean(entry[1])),
    );
    const query = params.toString();
    return apiRequest(`${base(org)}/bank-transactions${query ? `?${query}` : ""}`);
  },
  record: (org: string, body: NewBankTransaction): Promise<ApiResult<BankTransaction & Refusal>> =>
    apiRequest(`${base(org)}/bank-transactions`, { method: "POST", body }),
  taxDefault: (org: string, query: TaxDefaultQuery): Promise<ApiResult<TaxDefault & Refusal>> =>
    apiRequest(`${base(org)}/bank-transactions/tax-default?${taxDefaultQuery(query)}`),
  void: (org: string, id: string, date?: string): Promise<ApiResult<BankTransaction & Refusal>> =>
    apiRequest(`${base(org)}/bank-transactions/${id}/void`, {
      method: "POST",
      body: date ? { date } : {},
    }),
};

export interface RegisterRow {
  id: string;
  date: string;
  journal: { id: string; number: string; type: string };
  status: "posted" | "reversed";
  contact: { id: string; name: string } | null;
  description: string;
  reference: string;
  transaction: string | null;
  voided: boolean;
  received: string | null;
  spent: string | null;
  balance: string;
}

export interface RegisterFilters {
  date_from?: string;
  date_to?: string;
  contact?: string;
  amount_min?: string;
  amount_max?: string;
  status?: "posted" | "reversed";
}

export function registerQuery(filters: RegisterFilters, exportAs?: "csv" | "xlsx"): string {
  const params = new URLSearchParams(
    Object.entries(filters).filter((entry): entry is [string, string] => Boolean(entry[1])),
  );
  if (exportAs) params.set("export", exportAs);
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function registerUrl(
  org: string,
  id: string,
  filters: RegisterFilters = {},
  exportAs?: "csv" | "xlsx",
): string {
  return `${base(org)}/bank-accounts/${id}/register${registerQuery(filters, exportAs)}`;
}

export const registerApi = {
  get: (
    org: string,
    id: string,
    filters: RegisterFilters = {},
  ): Promise<ApiResult<{ account: BankAccount; results: RegisterRow[] }>> =>
    apiRequest(registerUrl(org, id, filters)),
};
