/**
 * Client for the organisation directory API (V-01, docs/architecture/directory.md):
 * `GET /api/v1/practice/orgs` and the saved views `/api/v1/practice/views`. Every call resolves
 * (never throws on an HTTP error): screens branch on `status`.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export const DIRECTORY_URL = "/api/v1/practice/orgs";
export const VIEWS_URL = "/api/v1/practice/views";

export type DirectoryStatus = "trial" | "paid" | "demo" | "read_only" | "archived";

/** One organisation row; only `id`, `name` and the requested columns' fields are present. */
export interface DirectoryRow {
  id: string;
  name: string;
  legal_name?: string;
  bn?: string;
  owner_name?: string;
  owner_email?: string;
  industry?: string;
  province?: string;
  package?: string;
  package_name?: string;
  status?: DirectoryStatus;
  trial_ends_at?: string | null;
  trial_days_left?: number | null;
  fye_month?: number;
  fye_day?: number;
  gst_cycle?: string;
  payroll_enabled?: boolean;
  overdue_count?: number;
  unfiled_count?: number;
  tags?: string[];
  /** Groups the organisation is filed in directly (badges, V-02-T08). */
  groups?: { id: string; name: string }[];
}

export interface FacetValue {
  value: string;
  label: string;
  count: number;
  /** Group facet: the group's level in the tree (1 = top). */
  depth?: number;
}

/** One group-by header (V-02-T08): a group (null = no group), its count and its rows' ids. */
export interface DirectoryGrouping {
  group: { id: string; name: string; depth: number; parent: string | null } | null;
  count: number;
  organisations: string[];
}

export const FILTER_KEYS = [
  "package",
  "status",
  "province",
  "fye",
  "gst_cycle",
  "payroll",
  "overdue",
  "unfiled",
  "tag",
  "group",
] as const;
export type FilterKey = (typeof FILTER_KEYS)[number];

export interface DirectoryPage {
  practice: { id: string; name: string };
  count: number;
  total: number;
  page: number;
  page_size: number;
  pages: number;
  columns: string[];
  results: DirectoryRow[];
  facets?: Record<FilterKey, FacetValue[]>;
  grouping?: DirectoryGrouping[];
}

/** Search, filters, sort, columns and density: what a saved view stores. */
export interface DirectoryState {
  q: string;
  filters: Partial<Record<FilterKey, string[]>>;
  archived: boolean;
  sort: string[];
  /** Shown columns, in order. */
  columns: string[];
  density: "comfortable" | "compact";
}

export interface SavedView {
  id: string;
  practice: string;
  name: string;
  filters: Partial<Record<FilterKey, string[]>> & { q?: string; archived?: "include" | "exclude" };
  columns: string[];
  sort: string[];
  density: "comfortable" | "compact";
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface ListOptions {
  practice: string;
  q?: string;
  filters?: DirectoryState["filters"];
  archived?: boolean;
  sort?: string[];
  pageSize?: number;
  columns?: string[];
  facets?: boolean;
  /** "group": ask for the group-by headers (V-02-T08). */
  groupBy?: "group" | "";
  signal?: AbortSignal;
}

/** Query string of a directory request (filters repeat: `province=ON&province=QC`). */
export function directoryQuery(options: ListOptions): string {
  const params = new URLSearchParams();
  params.set("practice", options.practice);
  if (options.q?.trim()) params.set("q", options.q.trim());
  for (const key of FILTER_KEYS) {
    for (const value of options.filters?.[key] ?? []) params.append(key, value);
  }
  if (options.archived) params.set("archived", "include");
  if (options.sort?.length) params.set("sort", options.sort.join(","));
  params.set("page_size", String(options.pageSize ?? 2000));
  if (options.columns?.length) params.set("columns", options.columns.join(","));
  if (options.facets === false) params.set("facets", "0");
  if (options.groupBy) params.set("group_by", options.groupBy);
  return params.toString();
}

async function list(options: ListOptions): Promise<ApiResult<DirectoryPage>> {
  return apiRequest<DirectoryPage>(`${DIRECTORY_URL}?${directoryQuery(options)}`, {
    fetcher: (input, init) => fetch(input, { ...init, signal: options.signal }),
  });
}

export type ViewInput = Partial<Omit<SavedView, "id" | "created_at" | "updated_at">>;

export const directoryApi = {
  list,
  views: (practice: string) =>
    apiRequest<SavedView[]>(`${VIEWS_URL}?practice=${encodeURIComponent(practice)}`),
  createView: (body: ViewInput) => apiRequest<SavedView>(VIEWS_URL, { method: "POST", body }),
  updateView: (id: string, body: ViewInput) =>
    apiRequest<SavedView>(`${VIEWS_URL}/${id}`, { method: "PATCH", body }),
  deleteView: (id: string) => apiRequest<unknown>(`${VIEWS_URL}/${id}`, { method: "DELETE" }),
};

/** A saved view's state, in the screen's shape. */
export function viewToState(view: SavedView, fallbackColumns: string[]): DirectoryState {
  const { q, archived, ...filters } = view.filters;
  return {
    q: q ?? "",
    filters,
    archived: archived === "include",
    sort: view.sort,
    columns: view.columns.length ? view.columns : fallbackColumns,
    density: view.density,
  };
}

/** The screen's state, in the API's shape (empty filters dropped). */
export function stateToView(state: DirectoryState): ViewInput {
  const filters: SavedView["filters"] = {};
  for (const key of FILTER_KEYS) {
    const values = state.filters[key];
    if (values?.length) filters[key] = values;
  }
  if (state.q.trim()) filters.q = state.q.trim();
  if (state.archived) filters.archived = "include";
  return { filters, columns: state.columns, sort: state.sort, density: state.density };
}

/** Two states that a saved view would store the same way. */
export function sameState(a: DirectoryState, b: DirectoryState): boolean {
  return JSON.stringify(stateToView(a)) === JSON.stringify(stateToView(b));
}

/** "123456782" → "123 456 782". */
export function formatBn(bn: string | undefined): string {
  if (!bn) return "";
  return bn.replace(/^(\d{3})(\d{3})(\d{3})$/, "$1 $2 $3");
}
