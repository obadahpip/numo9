/**
 * Reports API client (K-01-T11): `/api/v1/o/<org>/reports…` — the catalogue, a run (the report
 * body: header, columns, rows, totals, notes), exports, drill-down, favourites, layouts and cell
 * notes. A report outside the package answers 402 naming its product.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export interface ReportParam {
  name: string;
  kind: "date" | "choice" | "bool" | "int" | "text";
  default: string | number | boolean | null;
  choices: string[];
  required: boolean;
}

export interface ReportSummary {
  id: string;
  slug: string;
  name: string;
  description: string;
  category: string;
  feature: string;
  params: ReportParam[];
  /** The product of `feature` and its name ("Tax"): what a gated report names. */
  product: string;
  product_name: string;
  available: boolean;
  favourite: boolean;
}

export type LayoutStatus = "draft" | "published" | "custom";

export interface LayoutRowConfig {
  key: string;
  label?: string;
  hidden?: boolean;
}

export interface LayoutConfig {
  rows?: LayoutRowConfig[];
  text_blocks?: { after?: string; text: string }[];
}

export interface ReportLayout {
  id: string;
  report: string;
  name: string;
  status: LayoutStatus;
  version: number;
  params: Record<string, string>;
  config: LayoutConfig;
  notes: string;
  practice: string | null;
  published_at: string | null;
  updated_at: string | null;
}

export interface Catalogue {
  categories: { key: string; reports: ReportSummary[] }[];
  favourites: string[];
  drafts: ReportLayout[];
  published: ReportLayout[];
  custom: ReportLayout[];
}

export type RowKind = "section" | "row" | "total" | "text";

export interface ReportRowData {
  key: string;
  label: string;
  kind: RowKind;
  level: number;
  values: (string | null)[];
  drill: Record<string, string> | null;
  notes?: Record<string, string>;
}

export interface ReportHeader {
  title: string;
  display_name: string;
  legal_name: string;
  period_label: string;
  status_label: string;
  basis_label: string;
  book_label: string;
}

export interface ReportAlert {
  code: string;
  level: "error" | "warning";
  message: string;
}

export interface ReportBody {
  report: string;
  params: Record<string, string | number | boolean | null>;
  columns: { key: string; label: string }[];
  rows: ReportRowData[];
  totals: ReportRowData[];
  /** Integrity problems (K-02-T05): an `error` is a red banner above the statement. */
  alerts?: ReportAlert[];
  header: ReportHeader;
  notes: string;
  unplaced_notes?: { row: string; column: string; text: string }[];
  layout?: ReportLayout;
}

export interface DrillLine {
  date: string | null;
  journal: string;
  narration: string;
  description: string;
  contact: string;
  debit: string;
  credit: string;
  amount: string;
  status: string;
  /** The source document (an invoice, a bank transaction) or the journal itself. */
  source: { type: string; url: string; journal_url: string };
}

export interface DrillResult {
  account: { id: string; code: string; name: string };
  total: string;
  count: number;
  page: number;
  pages: number;
  lines: DrillLine[];
}

export interface Refusal {
  code?: string;
  detail?: string;
  product?: string;
  product_name?: string;
}

export type ExportFile = "pdf" | "xlsx" | "csv";
export const EXPORT_FILES: readonly ExportFile[] = ["pdf", "xlsx", "csv"];

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/reports`;

export function queryString(params: Record<string, string | undefined | null>): string {
  const query = new URLSearchParams(
    Object.entries(params).filter((entry): entry is [string, string] => Boolean(entry[1])),
  ).toString();
  return query ? `?${query}` : "";
}

export function exportUrl(
  org: string,
  report: string,
  params: Record<string, string | undefined>,
  file: ExportFile,
): string {
  return `${base(org)}/${encodeURIComponent(report)}/export${queryString({ ...params, file })}`;
}

export const reportsApi = {
  catalogue: (org: string): Promise<ApiResult<Catalogue>> => apiRequest(base(org)),
  run: (
    org: string,
    report: string,
    params: Record<string, string | undefined>,
  ): Promise<ApiResult<ReportBody & Refusal>> =>
    apiRequest(`${base(org)}/${encodeURIComponent(report)}/run${queryString(params)}`),
  drill: (
    org: string,
    report: string,
    params: Record<string, string | undefined>,
  ): Promise<ApiResult<DrillResult & Refusal>> =>
    apiRequest(`${base(org)}/${encodeURIComponent(report)}/drill${queryString(params)}`),
  favourite: (org: string, report: string, on: boolean): Promise<ApiResult<unknown>> =>
    apiRequest(`${base(org)}/${encodeURIComponent(report)}/favourite`, {
      method: on ? "PUT" : "DELETE",
    }),
  layouts: (org: string, report: string): Promise<ApiResult<{ results: ReportLayout[] }>> =>
    apiRequest(`${base(org)}/${encodeURIComponent(report)}/layouts`),
  saveLayout: (
    org: string,
    report: string,
    body: {
      name: string;
      status: "draft" | "custom";
      params: Record<string, string>;
      config: LayoutConfig;
      notes: string;
    },
  ): Promise<ApiResult<ReportLayout & Refusal>> =>
    apiRequest(`${base(org)}/${encodeURIComponent(report)}/layouts`, { method: "POST", body }),
  publish: (org: string, id: string): Promise<ApiResult<ReportLayout & Refusal>> =>
    apiRequest(`${base(org)}/layouts/${id}/publish`, { method: "POST" }),
  setNote: (
    org: string,
    report: string,
    body: { row: string; column: string; text: string; layout?: string },
  ): Promise<ApiResult<{ row: string; column: string; text: string } & Refusal>> =>
    apiRequest(`${base(org)}/${encodeURIComponent(report)}/notes`, { method: "PUT", body }),
};
