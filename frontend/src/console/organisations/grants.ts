/** Product grants of an organisation (U-03-T14): `/api/v1/platform/organisations/<id>/overrides`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export interface ProductGrant {
  id: string;
  product: string;
  product_name: string;
  expires_at: string;
  reason: string;
  granted_by: string;
  created_at: string;
  removed_at: string | null;
  state: "active" | "expired" | "removed";
}

export interface GrantList {
  overrides: ProductGrant[];
  products: { code: string; name: string }[];
  max_days: number;
}

const url = (org: string, suffix = "") =>
  `/api/v1/platform/organisations/${encodeURIComponent(org)}/overrides${suffix}`;

export const listGrants = (org: string): Promise<ApiResult<GrantList>> =>
  apiRequest<GrantList>(url(org));

export const grantProduct = (
  org: string,
  grant: { product: string; days: number; reason: string },
): Promise<ApiResult<ProductGrant | Record<string, string[]>>> =>
  apiRequest<ProductGrant | Record<string, string[]>>(url(org), { method: "POST", body: grant });

export const removeGrant = (org: string, id: string): Promise<ApiResult<unknown>> =>
  apiRequest<unknown>(url(org, `/${encodeURIComponent(id)}`), { method: "DELETE" });
