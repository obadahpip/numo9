/**
 * Client for the roles, assignments, approval limits and catalogue API (A-03-T09,
 * docs/architecture/permissions.md § API). Organisation routes live under
 * `/api/v1/o/<org>/…` (the organisation's public id, as in the app URL).
 *
 * Every call resolves (never throws on an HTTP error): screens branch on `status` and the error
 * `code` (`permission.denied` → the "why can't I?" panel, A-03-T14).
 */
import { apiRequest, type ApiResult, type Numo9Error } from "@/auth/client";

export interface RoleRef {
  id: string;
  /** System roles only, e.g. "owner"; "" for custom roles. */
  key: string;
  name: string;
  scope: "organisation" | "practice" | "platform";
  is_system: boolean;
}

export interface Role extends RoleRef {
  description: string;
  editable: boolean;
  assignable: boolean;
  permissions: string[];
  holders: number;
}

export interface PracticeAccess {
  id: string;
  name: string;
  role: string;
  role_name: string;
}

export interface Member {
  id: string;
  name: string;
  email: string;
  kind: "member" | "practice";
  main_role: RoleRef | null;
  practices: PracticeAccess[];
  roles: RoleRef[];
}

export interface PendingInvitation {
  id: string;
  email: string;
  role: string;
  expires_at: string;
  inviter_name: string;
}

export interface CataloguePermission {
  key: string;
  label: string;
  module: string;
  risk: "low" | "medium" | "high" | "critical";
  risk_label: string;
  scope: "organisation" | "practice" | "platform";
  owner_only: boolean;
  read_only: boolean;
}

export interface Catalogue {
  modules: { key: string; label: string }[];
  permissions: CataloguePermission[];
}

export type DocType = "journal" | "bill" | "purchase_order" | "pay_run";

export const DOC_TYPES: readonly DocType[] = ["journal", "bill", "purchase_order", "pay_run"];

export interface ApprovalLimit {
  id: string;
  doc_type: DocType;
  /** CAD, two decimals, e.g. "5000.00". */
  max_amount: string;
  user: { id: string; name: string } | null;
  role: RoleRef | null;
  updated_at: string;
}

/** Error body of the Numo9 API, plus the fields some errors add (A-03-T07, T09, T14). */
export interface ApiError extends Numo9Error {
  permissions?: string[];
  explain?: Explain;
}

/** "Why can't I?" payload of `403 permission.denied` (A-03-T14, backend numo9/rbac/explain.py). */
export interface Explain {
  rule: "permission";
  permission: {
    key: string;
    label: string;
    module: string;
    module_label: string;
    risk: string;
    risk_label: string;
  };
  holders: { id: string; name: string; roles: string[] }[];
  holders_total: number;
  managers: { id: string; name: string }[];
  can_request: boolean;
}

/** An open access request (`…/access-requests`). */
export interface AccessRequest {
  id: string;
  requester: { id: string; name: string };
  permission: Explain["permission"];
  note: string;
  created_at: string;
  notified: number;
  already_open: boolean;
}

export const orgApi = (org: string, path: string) => `/api/v1/o/${encodeURIComponent(org)}/${path}`;

export const CATALOGUE_URL = "/api/v1/permissions/catalogue";

export const usersRolesApi = {
  members: (org: string) => apiRequest<Member[] | ApiError>(orgApi(org, "members")),
  invitations: (org: string) =>
    apiRequest<PendingInvitation[] | ApiError>(orgApi(org, "invitations")),
  roles: (org: string) => apiRequest<Role[] | ApiError>(orgApi(org, "roles")),
  role: (org: string, id: string) => apiRequest<Role | ApiError>(orgApi(org, `roles/${id}`)),
  catalogue: () => apiRequest<Catalogue | ApiError>(CATALOGUE_URL),
  createRole: (
    org: string,
    body: { name: string; description?: string; permissions: string[]; copy_from?: string },
  ) => apiRequest<Role | ApiError>(orgApi(org, "roles"), { method: "POST", body }),
  updateRole: (
    org: string,
    id: string,
    body: { name?: string; description?: string; permissions?: string[] },
  ) => apiRequest<Role | ApiError>(orgApi(org, `roles/${id}`), { method: "PATCH", body }),
  deleteRole: (org: string, id: string) =>
    apiRequest<ApiError>(orgApi(org, `roles/${id}`), { method: "DELETE" }),
  assignRole: (org: string, user: string, role: string) =>
    apiRequest<Member | ApiError>(orgApi(org, `members/${user}/roles`), {
      method: "POST",
      body: { role },
    }),
  unassignRole: (org: string, user: string, role: string) =>
    apiRequest<ApiError>(orgApi(org, `members/${user}/roles/${role}`), { method: "DELETE" }),
  invite: (org: string, email: string, role: string) =>
    apiRequest<PendingInvitation | ApiError>("/api/v1/invitations", {
      method: "POST",
      body: { kind: "organisation_user", email, role, organisation: org },
    }),
  limits: (org: string) => apiRequest<ApprovalLimit[] | ApiError>(orgApi(org, "approval-limits")),
  createLimit: (
    org: string,
    body: { doc_type: DocType; max_amount: string; user?: string; role?: string },
  ) =>
    apiRequest<ApprovalLimit | ApiError>(orgApi(org, "approval-limits"), {
      method: "POST",
      body,
    }),
  updateLimit: (org: string, id: string, maxAmount: string) =>
    apiRequest<ApprovalLimit | ApiError>(orgApi(org, `approval-limits/${id}`), {
      method: "PATCH",
      body: { max_amount: maxAmount },
    }),
  deleteLimit: (org: string, id: string) =>
    apiRequest<ApiError>(orgApi(org, `approval-limits/${id}`), { method: "DELETE" }),
  requestAccess: (org: string, permission: string, note: string) =>
    apiRequest<AccessRequest | ApiError>(orgApi(org, "access-requests"), {
      method: "POST",
      body: { permission, note },
    }),
  accessRequests: (org: string) =>
    apiRequest<AccessRequest[] | ApiError>(orgApi(org, "access-requests")),
  closeAccessRequest: (org: string, id: string) =>
    apiRequest<ApiError>(orgApi(org, `access-requests/${id}`), { method: "DELETE" }),
};

export function isOk<Body>(result: ApiResult<Body | ApiError>): result is ApiResult<Body> {
  return result.status >= 200 && result.status < 300;
}

/** The message to show for a refused request: the API's own (localised) text when it sent one. */
export function errorText(body: unknown): string | undefined {
  if (body === null || typeof body !== "object") return undefined;
  const error = body as Record<string, unknown>;
  if (typeof error.detail === "string") return error.detail;
  for (const value of Object.values(error)) {
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  }
  return undefined;
}
