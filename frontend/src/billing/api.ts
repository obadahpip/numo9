/** Billing API client (U-04): `/api/v1/o/<org>/billing…` — the organisation's owner only. */
import { apiRequest, type ApiResult } from "@/auth/client";

export type Interval = "month" | "year";

export interface BillingSubscription {
  status: "trialing" | "active" | "past_due" | "read_only" | "cancelled" | "demo";
  package: { code: string; name: string } | null;
  interval: Interval;
  amount_cents: number | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  payment_method_type: "" | "card" | "acss_debit";
  grace_until: string | null;
  paying: boolean;
}

export interface BillingOverview {
  billing_available: boolean;
  subscription: BillingSubscription | null;
  pending_change: {
    package: { code: string; name: string };
    interval: Interval;
    effective_at: string;
  } | null;
  packages: { code: string; name: string; prices: Partial<Record<Interval, number>> }[];
  invoices: {
    id: string;
    number: string;
    status: string;
    issued_at: string | null;
    total_cents: number;
    currency: string;
    pdf_url: string;
    hosted_url: string;
  }[];
}

export interface ChangePreview {
  kind: "upgrade" | "downgrade";
  package: string;
  interval: Interval;
  amount_cents: number;
  charged_today_cents: number;
  currency: string;
  effective_at: string;
  proration_date: number;
}

export interface ExportState {
  job: string | null;
  status: string | null;
  url: string | null;
  expires_at: string | null;
  created_at: string | null;
}

export const billingUrl = (org: string, suffix = "") =>
  `/api/v1/o/${encodeURIComponent(org)}/billing${suffix}`;

export const getOverview = (org: string): Promise<ApiResult<BillingOverview>> =>
  apiRequest<BillingOverview>(billingUrl(org));

export const startCheckout = (
  org: string,
  body: { package: string; interval: Interval },
): Promise<ApiResult<{ url: string }>> =>
  apiRequest<{ url: string }>(billingUrl(org, "/checkout"), { method: "POST", body });

export const previewChange = (
  org: string,
  pkg: string,
  interval: Interval,
): Promise<ApiResult<ChangePreview>> =>
  apiRequest<ChangePreview>(
    billingUrl(
      org,
      `/change/preview?package=${encodeURIComponent(pkg)}&interval=${encodeURIComponent(interval)}`,
    ),
  );

export const changePackage = (
  org: string,
  body: { package: string; interval: Interval; proration_date?: number },
): Promise<ApiResult<ChangePreview>> =>
  apiRequest<ChangePreview>(billingUrl(org, "/change"), { method: "POST", body });

export const openPortal = (org: string): Promise<ApiResult<{ url: string }>> =>
  apiRequest<{ url: string }>(billingUrl(org, "/portal"), { method: "POST" });

export const cancelSubscription = (
  org: string,
  resume = false,
): Promise<ApiResult<{ cancel_at_period_end: boolean; export: ExportState | null }>> =>
  apiRequest(billingUrl(org, "/cancel"), { method: "POST", body: { resume } });

export const getExport = (org: string): Promise<ApiResult<ExportState>> =>
  apiRequest<ExportState>(billingUrl(org, "/export"));
