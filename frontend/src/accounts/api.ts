/** Chart of accounts API client (C-01-T09): `/api/v1/o/<org>/accounts…`, `/gifi`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export type AccountType = "asset" | "liability" | "equity" | "revenue" | "expense";

export interface Account {
  id: string;
  code: string;
  name: string;
  description: string;
  type: AccountType;
  type_label: string;
  subtype: string;
  subtype_label: string;
  parent: string | null;
  depth: number;
  has_children: boolean;
  system_role: string;
  system_role_label: string;
  is_bank: boolean;
  gifi: { code: string; description: string } | null;
  require_contact: boolean;
  require_tracking: boolean;
  require_attachment: boolean;
  default_tax_key: string;
  status: "active" | "archived";
  archived_at: string | null;
  balance: { accounting: string; tax: string };
}

export interface GifiOption {
  code: string;
  description: string;
  section: string;
}

export interface BulkResult {
  action: string;
  done: number;
  failed: number;
  results: { id: string; code?: string; ok: boolean; detail?: string }[];
}

export type AccountChanges = Partial<
  Pick<
    Account,
    | "code"
    | "name"
    | "description"
    | "require_contact"
    | "require_tracking"
    | "require_attachment"
    | "default_tax_key"
  >
> & { gifi?: string | null };

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/accounts`;

export const accountsApi = {
  list: (org: string, status: "active" | "archived" | "all") =>
    apiRequest<{ results: Account[]; count: number }>(`${base(org)}?status=${status}`),
  update: (org: string, id: string, changes: AccountChanges): Promise<ApiResult<Account>> =>
    apiRequest<Account>(`${base(org)}/${id}`, { method: "PATCH", body: changes }),
  renumber: (org: string, id: string, code: string): Promise<ApiResult<Account>> =>
    apiRequest<Account>(`${base(org)}/${id}/renumber`, { method: "POST", body: { code } }),
  archive: (org: string, id: string): Promise<ApiResult<Account>> =>
    apiRequest<Account>(`${base(org)}/${id}/archive`, { method: "POST" }),
  restore: (org: string, id: string): Promise<ApiResult<Account>> =>
    apiRequest<Account>(`${base(org)}/${id}/restore`, { method: "POST" }),
  bulk: (org: string, ids: string[], action: "archive" | "restore") =>
    apiRequest<BulkResult>(`${base(org)}/bulk`, {
      method: "POST",
      body: { accounts: ids, action },
    }),
  gifi: (org: string, q: string, type: AccountType) =>
    apiRequest<{ results: GifiOption[] }>(
      `/api/v1/o/${encodeURIComponent(org)}/gifi?q=${encodeURIComponent(q)}&type=${type}`,
    ),
};

/** The server's explanation of a refusal (`{detail}`), or undefined. */
export function refusal(result: ApiResult<unknown>): string | undefined {
  const body = result.body as { detail?: unknown } | undefined;
  return typeof body?.detail === "string" ? body.detail : undefined;
}
