/**
 * Document calculation API client (D-01-T09): `POST /api/v1/o/<org>/documents/<side>/calculate`
 * and `…/posting-preview`. The editors show the client mirror's figures at once and replace them
 * with the server's (server-authoritative).
 */
import { apiRequest, type ApiResult } from "@/auth/client";

import type { DiscountType, TaxMode } from "./calculator";

export type DocumentSide = "sales" | "purchases";

export interface CalculateLine {
  account?: string | null;
  quantity: string;
  unit_price: string;
  discount_type: DiscountType;
  discount_value: string;
  tax_code?: string | null;
  description?: string;
}

export interface CalculateRequest {
  kind?: string;
  date: string;
  tax_mode: TaxMode;
  discount_type: DiscountType;
  discount_value: string;
  contact?: string | null;
  lines: CalculateLine[];
}

export interface CalculatedLine {
  gross: string;
  line_discount: string;
  net: string;
  discount_share: string;
  taxable: string;
  exclusive: string;
  tax: string;
  taxes: { key: string; rate: string; amount: string }[];
}

export interface LineProblem {
  line: number;
  field: string;
  code: string;
  message: string;
}

export interface CalculateResponse {
  kind: string;
  tax_mode: TaxMode;
  lines: CalculatedLine[];
  subtotal: string;
  discount_total: string;
  tax_total: string;
  total: string;
  net_total: string;
  tax_included: boolean;
  tax_by_component: { key: string; name: string; amount: string }[];
  problems: LineProblem[];
}

export interface PostingPreviewResponse extends Omit<CalculateResponse, "problems"> {
  journal: {
    lines: {
      account: { id: string; code: string; name: string };
      debit: string;
      credit: string;
      description: string;
      tax_code: string;
    }[];
    debits: string;
    credits: string;
    complete: boolean;
  };
}

const base = (org: string, side: DocumentSide) =>
  `/api/v1/o/${encodeURIComponent(org)}/documents/${side}`;

export const documentsApi = {
  calculate: (
    org: string,
    side: DocumentSide,
    body: CalculateRequest,
  ): Promise<ApiResult<CalculateResponse>> =>
    apiRequest(`${base(org, side)}/calculate`, { method: "POST", body }),
  postingPreview: (
    org: string,
    side: DocumentSide,
    body: CalculateRequest,
  ): Promise<ApiResult<PostingPreviewResponse & { code?: string; problems?: LineProblem[] }>> =>
    apiRequest(`${base(org, side)}/posting-preview`, { method: "POST", body }),
};
