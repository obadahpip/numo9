/**
 * Client for the platform packages API (U-02-T07, docs/architecture/packages-pricing.md):
 * `/api/v1/platform/packages…` (platform.catalogue.manage). Every call resolves (never throws on
 * an HTTP error); validation errors come back in field form `{field: ["message"]}`.
 */
import { apiRequest, type ApiResult, type Numo9Error } from "@/auth/client";

export const PACKAGES_API = "/api/v1/platform/packages";
export const PROMOS_API = `${PACKAGES_API}/promo-codes`;

export type PackageStatus = "draft" | "active" | "retired";
export type Interval = "month" | "year";
export type PriceState = "past" | "current" | "scheduled";
export type Texts = Partial<Record<"en-CA" | "fr-CA", string>>;

export interface PackagePrice {
  id: string;
  interval: Interval;
  interval_label: string;
  amount_cents: number;
  currency: string;
  tax_behaviour: string;
  effective_from: string;
  effective_to: string | null;
  state: PriceState;
}

export interface NamedCode {
  code: string;
  name: string;
}

export interface PlatformPackage {
  code: string;
  name: string;
  name_i18n: Texts;
  description: string;
  description_i18n: Texts;
  status: PackageStatus;
  status_label: string;
  is_founding_eligible: boolean;
  limits: { max_org_users: number | null };
  sort: number;
  products: NamedCode[];
  subscriber_count: number;
  prices: PackagePrice[];
  current_prices: Record<Interval, PackagePrice | null>;
  today: string;
  created_at: string;
  updated_at: string;
}

export interface PackageInput {
  code?: string;
  name_i18n: Texts;
  description_i18n: Texts;
  products: string[];
  limits: { max_org_users: number | null };
  is_founding_eligible: boolean;
}

export interface PriceImpact {
  affected_subscriptions: number;
  current: PackagePrice | null;
}

export type PromoKind = "percent" | "fixed";
export type PromoDuration = "once" | "repeating" | "forever";
export type PromoStatus = "active" | "used_up" | "expired";

export interface PromoCode {
  code: string;
  description: string;
  kind: PromoKind;
  kind_label: string;
  percent_off: number | null;
  amount_off_cents: number | null;
  currency: string;
  duration: PromoDuration;
  duration_label: string;
  duration_months: number | null;
  max_redemptions: number | null;
  redemptions_count: number;
  expires_at: string | null;
  packages: NamedCode[];
  status: PromoStatus;
  status_label: string;
  created_at: string;
}

export interface PromoInput {
  code: string;
  description: string;
  kind: PromoKind;
  percent_off: number | null;
  amount_off_cents: number | null;
  duration: PromoDuration;
  duration_months: number | null;
  max_redemptions: number | null;
  expires_at: string | null;
  packages: string[];
}

export type ApiError = Numo9Error;

/**
 * Field errors of a 400 answer: `{field: "first message"}`. A request-level error
 * (`{detail, code}`) has none — `code` is also a field of packages and promo codes.
 */
export function fieldErrors(body: unknown): Record<string, string> {
  const result: Record<string, string> = {};
  if (typeof body !== "object" || body === null || errorText(body) !== null) return result;
  for (const [field, value] of Object.entries(body)) {
    if (Array.isArray(value) && typeof value[0] === "string") result[field] = value[0];
    else if (typeof value === "object" && value !== null) {
      // nested serializer errors, e.g. {limits: {max_org_users: ["…"]}}
      const nested = Object.values(value as Record<string, unknown>).find(Array.isArray);
      if (nested && typeof nested[0] === "string") result[field] = nested[0];
    }
  }
  return result;
}

export function errorText(body: unknown): string | null {
  if (typeof body === "object" && body !== null && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}

export const ok = (status: number) => status >= 200 && status < 300;

const url = (code: string) => `${PACKAGES_API}/${encodeURIComponent(code)}`;

export const packagesApi = {
  list: (): Promise<ApiResult<{ packages: PlatformPackage[] } | ApiError>> =>
    apiRequest(PACKAGES_API),
  get: (code: string): Promise<ApiResult<PlatformPackage | ApiError>> => apiRequest(url(code)),
  create: (input: PackageInput): Promise<ApiResult<PlatformPackage | ApiError>> =>
    apiRequest(PACKAGES_API, { method: "POST", body: input }),
  update: (code: string, input: PackageInput): Promise<ApiResult<PlatformPackage | ApiError>> =>
    apiRequest(url(code), { method: "PATCH", body: input }),
  remove: (code: string): Promise<ApiResult<ApiError>> =>
    apiRequest(url(code), { method: "DELETE" }),
  activate: (code: string): Promise<ApiResult<PlatformPackage | ApiError>> =>
    apiRequest(`${url(code)}/activate`, { method: "POST" }),
  retire: (code: string): Promise<ApiResult<PlatformPackage | ApiError>> =>
    apiRequest(`${url(code)}/retire`, { method: "POST" }),
  impact: (
    code: string,
    interval: Interval,
    effectiveFrom: string,
  ): Promise<ApiResult<PriceImpact | ApiError>> =>
    apiRequest(
      `${url(code)}/prices/impact?interval=${interval}&effective_from=${encodeURIComponent(effectiveFrom)}`,
    ),
  schedulePrice: (
    code: string,
    input: { interval: Interval; amount_cents: number; effective_from: string },
  ): Promise<
    ApiResult<
      { price: PackagePrice; affected_subscriptions: number; package: PlatformPackage } | ApiError
    >
  > => apiRequest(`${url(code)}/prices`, { method: "POST", body: input }),
  deletePrice: (code: string, id: string): Promise<ApiResult<ApiError>> =>
    apiRequest(`${url(code)}/prices/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

const promoUrl = (code: string) => `${PROMOS_API}/${encodeURIComponent(code)}`;

export const promosApi = {
  list: (): Promise<ApiResult<{ promo_codes: PromoCode[] } | ApiError>> => apiRequest(PROMOS_API),
  create: (input: PromoInput): Promise<ApiResult<PromoCode | ApiError>> =>
    apiRequest(PROMOS_API, { method: "POST", body: input }),
  expire: (code: string): Promise<ApiResult<PromoCode | ApiError>> =>
    apiRequest(`${promoUrl(code)}/expire`, { method: "POST" }),
};
