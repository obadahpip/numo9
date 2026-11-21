/**
 * Client for `GET /api/v1/o/<org>/search?q=…` (A-09-T05) and the user's permissions in the
 * organisation (`GET …/my-permissions`), which decide the quick-create actions offered (T06).
 * Every call resolves; screens branch on `status`.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export type MatchKind = "code" | "code_prefix" | "amount" | "text" | "similar";

export interface RecordResult {
  /** `contacts.contact`, `ledger.account`, `ledger.journalentry`, … */
  type: string;
  id: string;
  title: string;
  subtitle: string;
  code: string;
  amount: string | null;
  date: string | null;
  url: string;
  match: MatchKind;
  locked: boolean;
  reason: string | null;
}

export interface StaticResult {
  key: string;
  title: string;
  url: string;
  locked: boolean;
  reason: string | null;
}

export interface SearchResults {
  query: string;
  records: RecordResult[];
  settings: StaticResult[];
  reports: StaticResult[];
  navigation: StaticResult[];
}

export const EMPTY_RESULTS: SearchResults = {
  query: "",
  records: [],
  settings: [],
  reports: [],
  navigation: [],
};

export function searchOrg(
  org: string,
  query: string,
  fetcher?: typeof fetch,
): Promise<ApiResult<SearchResults>> {
  const url = `/api/v1/o/${encodeURIComponent(org)}/search?q=${encodeURIComponent(query)}`;
  return apiRequest<SearchResults>(url, { fetcher });
}

export function isSearchResults(body: unknown): body is SearchResults {
  const b = body as Partial<SearchResults> | null;
  return (
    !!b &&
    Array.isArray(b.records) &&
    Array.isArray(b.settings) &&
    Array.isArray(b.reports) &&
    Array.isArray(b.navigation)
  );
}

/** The user's permission keys here; `null` when unknown (the API still enforces). */
export async function myPermissions(org: string): Promise<Set<string> | null> {
  const result = await apiRequest<{ permissions?: unknown }>(
    `/api/v1/o/${encodeURIComponent(org)}/my-permissions`,
  );
  const keys = result.body.permissions;
  if (result.status !== 200 || !Array.isArray(keys)) return null;
  return new Set(keys.filter((key): key is string => typeof key === "string"));
}
