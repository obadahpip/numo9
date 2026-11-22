/** Tax codes and rates API client (G-01-T11): `/api/v1/o/<org>/tax/…`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export type TaxSide = "sales" | "purchase";
export type TaxCodeType = "taxable" | "zero_rated" | "exempt" | "out_of_scope";

export interface TaxCodeComponentRow {
  id: string;
  key: string;
  name: string;
  kind: "gst" | "hst" | "pst" | "qst";
  rate: string;
  recoverable_pct: string | null;
}

export interface TaxCode {
  id: string;
  code: string;
  version: number;
  name: string;
  name_i18n: Record<string, string>;
  side: TaxSide;
  type: TaxCodeType;
  type_label: string;
  province: string;
  effective_from: string;
  effective_to: string | null;
  expired: boolean;
  archived_at: string | null;
  itc_restriction_pct: string | null;
  rate: string;
  components: TaxCodeComponentRow[];
  usage_count: number;
  versions?: TaxCode[];
}

export interface TaxComponent {
  id: string;
  key: string;
  name: string;
  kind: "gst" | "hst" | "pst" | "qst";
  authority: string;
  rate: string;
  effective_from: string;
  effective_to: string | null;
  recoverable: boolean;
  side: "both" | "sales" | "purchase";
  control_account_sales: string | null;
  control_account_purchase: string | null;
}

export interface Calculation {
  net: string;
  tax: string;
  gross: string;
  claimable: string;
  cost: string;
  components: {
    key: string;
    name: string;
    rate: string;
    amount: string;
    claimable: string;
    cost: string;
  }[];
}

export interface CodesQuery {
  side?: TaxSide;
  date?: string;
  expired?: boolean;
  archived?: boolean;
  q?: string;
}

export interface NewTaxCode {
  code: string;
  name: string;
  name_fr?: string;
  side: TaxSide;
  type: TaxCodeType;
  province?: string;
  effective_from: string;
  effective_to?: string | null;
  itc_restriction_pct?: string | null;
  components: { component: string; recoverable_pct?: string | null }[];
}

export interface Refusal {
  code?: string;
  detail?: string;
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/tax`;

export function codesQuery(query: CodesQuery): string {
  const params = new URLSearchParams();
  if (query.side) params.set("side", query.side);
  if (query.date) params.set("date", query.date);
  if (query.expired) params.set("expired", "1");
  if (query.archived) params.set("archived", "1");
  if (query.q) params.set("q", query.q);
  const text = params.toString();
  return text ? `?${text}` : "";
}

export const taxApi = {
  codes: (org: string, query: CodesQuery = {}): Promise<ApiResult<{ results: TaxCode[] }>> =>
    apiRequest(`${base(org)}/codes${codesQuery(query)}`),
  code: (org: string, id: string): Promise<ApiResult<TaxCode>> =>
    apiRequest(`${base(org)}/codes/${id}`),
  components: (
    org: string,
    query: { key?: string; expired?: boolean } = {},
  ): Promise<ApiResult<{ results: TaxComponent[] }>> => {
    const params = new URLSearchParams();
    if (query.key) params.set("key", query.key);
    if (query.expired) params.set("expired", "1");
    const text = params.toString();
    return apiRequest(`${base(org)}/components${text ? `?${text}` : ""}`);
  },
  create: (org: string, body: NewTaxCode): Promise<ApiResult<TaxCode & Refusal>> =>
    apiRequest(`${base(org)}/codes`, { method: "POST", body }),
  version: (
    org: string,
    id: string,
    body: Pick<NewTaxCode, "effective_from" | "components"> & { name?: string },
  ): Promise<ApiResult<TaxCode & Refusal>> =>
    apiRequest(`${base(org)}/codes/${id}/versions`, { method: "POST", body }),
  archive: (org: string, id: string): Promise<ApiResult<TaxCode>> =>
    apiRequest(`${base(org)}/codes/${id}/archive`, { method: "POST" }),
  restore: (org: string, id: string): Promise<ApiResult<TaxCode>> =>
    apiRequest(`${base(org)}/codes/${id}/restore`, { method: "POST" }),
  calculate: (
    org: string,
    body: { code: string; amount: string; inclusive?: boolean; account?: string | null },
  ): Promise<ApiResult<Calculation & Refusal>> =>
    apiRequest(`${base(org)}/calculate`, { method: "POST", body }),
};
