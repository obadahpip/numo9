/**
 * Client for the entitlements bootstrap (U-03-T09, docs/architecture/entitlements.md):
 * `GET /api/v1/o/<org>/entitlements` — what the organisation may use now. Resolves (never throws).
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export type EntitlementMode = "full" | "read_only" | "none";

export interface PackageName {
  code: string;
  name: string;
}

export interface Entitlements {
  organisation: string;
  mode: EntitlementMode;
  /**
   * full: trialing, active, past_due, demo, no_subscription; read_only: payment_failed,
   * trial_ended, cancelled, platform, read_only; none: no_organisation.
   */
  reason: string;
  /** ISO date-time the organisation became read-only (read_only), else null. */
  since: string | null;
  /** Payment overdue (reason past_due): full access until then (U-04-T13), else null. */
  grace_until?: string | null;
  /** Free trial (reason trialing, U-05-T10): when it ends (local 23:59:59), else null. */
  trial_ends_at?: string | null;
  /** Free trial: whole days left on the organisation's calendar (0 = the last day). */
  trial_days_left?: number | null;
  package: string | null;
  package_name: string | null;
  status: string | null;
  founding: boolean;
  products: string[];
  /** Products kept for reading only (read retention after a downgrade). */
  read_products: string[];
  features: string[];
  version: string;
  product_names: Record<string, string>;
  packages_by_product: Record<string, PackageName[]>;
  /** The organisation's time zone (dates in the read-only banner). */
  time_zone: string;
  viewer: { can_change_package: boolean };
}

export const entitlementsUrl = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/entitlements`;

export function getEntitlements(org: string): Promise<ApiResult<Entitlements>> {
  return apiRequest<Entitlements>(entitlementsUrl(org));
}

export function isEntitlements(body: unknown): body is Entitlements {
  return (
    typeof body === "object" &&
    body !== null &&
    "features" in body &&
    Array.isArray((body as { features: unknown }).features) &&
    "mode" in body
  );
}
