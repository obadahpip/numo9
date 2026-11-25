/**
 * Expense claims API client — the approver's view (E-04-T11): `/api/v1/o/<org>/expense-claims/<id>`
 * (detail with the tax split, mileage tiers, duplicate-receipt warnings and `can_approve`),
 * `/approve`, `/reject` (`reason`).
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
}

export interface Refusal {
  code?: string;
  detail?: string;
}

const base = (org: string, id: string) =>
  `/api/v1/o/${encodeURIComponent(org)}/expense-claims/${encodeURIComponent(id)}`;
type Result<T> = Promise<ApiResult<T & Refusal>>;

export const expenseClaimsApi = {
  get: (org: string, id: string): Result<ExpenseClaim> => apiRequest(base(org, id)),
  approve: (org: string, id: string): Result<ExpenseClaim> =>
    apiRequest(`${base(org, id)}/approve`, { method: "POST" }),
  reject: (org: string, id: string, reason: string): Result<ExpenseClaim> =>
    apiRequest(`${base(org, id)}/reject`, { method: "POST", body: { reason } }),
};
