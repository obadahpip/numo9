/** Approvals inbox API client (C-04-T08): `GET /api/v1/o/<org>/approvals`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export interface ApprovalItem {
  kind: string;
  id: string;
  title: string;
  subtitle: string;
  amount: string;
  date: string | null;
  url: string;
  submitted_by: { id: string; name: string } | null;
  submitted_at: string | null;
  created_by: { id: string; name: string } | null;
  can_approve: boolean;
  /** Why not: `self` (they wrote or submitted it), `limit`, `no_limit`. */
  blocked: "self" | "limit" | "no_limit" | null;
  limit: string | null;
}

export interface ApprovalsInbox {
  results: ApprovalItem[];
  kinds: { kind: string; label: string; count: number; can_approve: number }[];
  counts: { total: number; can_approve: number };
}

export const approvalsApi = {
  inbox: (org: string): Promise<ApiResult<ApprovalsInbox>> =>
    apiRequest(`/api/v1/o/${encodeURIComponent(org)}/approvals`),
};
