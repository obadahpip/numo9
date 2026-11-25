/** Tax settings API client (G-06-T07): `/api/v1/o/<org>/tax/settings…`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export type TaxBasis = "accrual" | "cash";
export type RoundingMode = "line" | "document";
export type Side = "sales" | "purchase";

export interface RestrictedAccount {
  id: string;
  code: string;
  name: string;
  pct: string;
}

export interface TaxSettings {
  basis: TaxBasis;
  rounding_mode: RoundingMode;
  quick_method: boolean;
  quick_method_from: string | null;
  /** side → account type → tax code key. */
  default_codes: Partial<Record<Side, Record<string, string>>>;
  restricted_itc_accounts: RestrictedAccount[];
  /** After a GST/HST stop, new sales lines default to out of scope (G-03b-T06). */
  out_of_scope_after_stop: boolean;
  /** Whether an active GST/HST or QST registration exists. */
  registered: boolean;
  /** After a basis change during the financial year. */
  basis_warning?: string;
}

export interface BasisCheck {
  changes: boolean;
  mid_year: boolean;
  warning: string;
}

export type SettingsChange = Partial<
  Pick<
    TaxSettings,
    | "rounding_mode"
    | "quick_method"
    | "quick_method_from"
    | "default_codes"
    | "out_of_scope_after_stop"
  >
> & { basis?: TaxBasis; basis_reason?: string };

/** 400: field → messages. */
export type SettingsErrors = Record<string, string[]>;

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/tax/settings`;

export const taxSettingsApi = {
  get: (org: string): Promise<ApiResult<TaxSettings>> => apiRequest(base(org)),
  save: (org: string, body: SettingsChange): Promise<ApiResult<TaxSettings | SettingsErrors>> =>
    apiRequest(base(org), { method: "PATCH", body }),
  basisCheck: (org: string, basis: TaxBasis): Promise<ApiResult<BasisCheck>> =>
    apiRequest(`${base(org)}/basis-check?basis=${basis}`),
  restrictItc: (
    org: string,
    account: string,
    pct: string | null,
  ): Promise<ApiResult<{ restricted_itc_accounts: RestrictedAccount[] } | SettingsErrors>> =>
    apiRequest(`${base(org)}/restricted-itc/${encodeURIComponent(account)}`, {
      method: "PUT",
      body: { pct },
    }),
};

/** The first message of a 400 body, whatever field it is on. */
export function firstError(body: unknown): string | undefined {
  if (!body || typeof body !== "object") return undefined;
  for (const value of Object.values(body as Record<string, unknown>)) {
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
    if (typeof value === "string") return value;
  }
  return undefined;
}

/** Account types that keep a default code, per side (as `tax.defaults` on the server). */
export const DEFAULT_TYPES: Record<Side, string[]> = {
  sales: ["revenue", "asset"],
  purchase: ["expense", "asset", "liability"],
};
