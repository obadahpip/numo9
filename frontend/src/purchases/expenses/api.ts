/**
 * Expense claims API client (numo9/purchases/expense_api.py): the claimant's form (E-04-T08/T09)
 * — list, create, edit, submit, the categories most used first, the CRA mileage rate with the
 * year-to-date kilometres, receipt upload — and the approver's view (E-04-T11): detail with the
 * tax split, mileage tiers, duplicate-receipt warnings and `can_approve`, `/approve`, `/reject`.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export type ClaimStatus = "draft" | "submitted" | "approved" | "rejected" | "paid";
export type Blocked = "self" | "permission" | "limit" | "status" | null;

export interface Person {
  id: string;
  name: string;
}

export interface ReceiptSplit {
  gross: string;
  net: string;
  tax: string;
  claimable: string;
  cost: string;
  expense: string;
}

export interface ClaimLine {
  id: string;
  kind: "receipt" | "mileage";
  date: string;
  description: string;
  account: { id: string; code: string; name: string } | null;
  amount: string;
  merchant?: string;
  tax_code?: { id: string; code: string } | null;
  receipt?: { id: string; name: string } | null;
  split?: ReceiptSplit;
  from_place?: string;
  to_place?: string;
  distance_km?: string;
  rate_detail?: { tier: "first" | "after"; km: string; rate: string; amount: string }[];
}

export interface ClaimWarning {
  code: string;
  line: string;
  message: string;
  claims: string[];
}

export interface ExpenseClaim {
  id: string;
  number: string;
  title: string;
  status: ClaimStatus;
  status_label: string;
  claimant: Person;
  submitted_by: Person | null;
  submitted_at: string | null;
  decided_by: Person | null;
  decided_at: string | null;
  rejection_reason: string;
  currency: string;
  total: string;
  notes: string;
  lines: ClaimLine[];
  warnings: ClaimWarning[];
  can_approve: boolean;
  blocked: Blocked;
  can_edit?: boolean;
  bill?: { id: string; number: string; status: string; amount_due: string; url: string } | null;
}

/** One line as the form sends it (receipt or mileage). */
export interface ClaimLineInput {
  kind: "receipt" | "mileage";
  date: string;
  description?: string;
  account: string | null;
  amount?: string;
  merchant?: string;
  tax_code?: string | null;
  receipt?: string | null;
  from_place?: string;
  to_place?: string;
  distance_km?: string;
}

export interface ClaimInput {
  title: string;
  notes?: string;
  lines: ClaimLineInput[];
}

export interface Category {
  id: string;
  code: string;
  name: string;
  used: number;
  itc_restriction_pct: string | null;
}

export interface CategoryList {
  categories: Category[];
  tax_codes: { id: string; code: string; name: string }[];
  default_tax_code: string | null;
}

export interface MileageRate {
  date: string;
  region: string;
  first_tier_rate: string;
  second_tier_rate: string;
  tier_threshold_km: number;
  year_to_date_km: string;
}

export interface ClaimRow {
  id: string;
  number: string;
  title: string;
  status: ClaimStatus;
  status_label: string;
  claimant: Person;
  total: string;
  url: string;
}

export interface ClaimPage {
  count: number;
  page: number;
  pages: number;
  counts: Record<ClaimStatus, number>;
  can_view_all: boolean;
  results: ClaimRow[];
}

export interface ReceiptUpload {
  document: { id: string; name: string };
  upload: { url: string; fields: Record<string, string> };
}

export interface ReceiptDocument {
  id: string;
  name: string;
  duplicate?: boolean;
}

export interface Refusal {
  code?: string;
  detail?: string;
}

const root = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/expense-claims`;
const base = (org: string, id: string) => `${root(org)}/${encodeURIComponent(id)}`;
type Result<T> = Promise<ApiResult<T & Refusal>>;

export const expenseClaimsApi = {
  list: (org: string, query = ""): Result<ClaimPage> =>
    apiRequest(`${root(org)}${query ? `?${query}` : ""}`),
  create: (org: string, claim: ClaimInput): Result<ExpenseClaim> =>
    apiRequest(root(org), { method: "POST", body: claim }),
  update: (org: string, id: string, claim: ClaimInput): Result<ExpenseClaim> =>
    apiRequest(base(org, id), { method: "PATCH", body: claim }),
  submit: (org: string, id: string): Result<ExpenseClaim> =>
    apiRequest(`${base(org, id)}/submit`, { method: "POST" }),
  categories: (org: string): Result<CategoryList> => apiRequest(`${root(org)}/categories`),
  mileageRate: (org: string, date: string, claim?: string): Result<MileageRate> =>
    apiRequest(
      `${root(org)}/mileage-rate?date=${encodeURIComponent(date)}${
        claim ? `&claim=${encodeURIComponent(claim)}` : ""
      }`,
    ),
  startReceipt: (org: string, name: string, size: number): Result<ReceiptUpload> =>
    apiRequest(`${root(org)}/receipts`, { method: "POST", body: { name, size } }),
  finishReceipt: (org: string, id: string): Result<ReceiptDocument> =>
    apiRequest(`${root(org)}/receipts/${encodeURIComponent(id)}/finalize`, { method: "POST" }),
  get: (org: string, id: string): Result<ExpenseClaim> => apiRequest(base(org, id)),
  approve: (org: string, id: string): Result<ExpenseClaim> =>
    apiRequest(`${base(org, id)}/approve`, { method: "POST" }),
  reject: (org: string, id: string, reason: string): Result<ExpenseClaim> =>
    apiRequest(`${base(org, id)}/reject`, { method: "POST", body: { reason } }),
};
