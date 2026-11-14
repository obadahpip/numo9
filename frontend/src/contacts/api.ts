/**
 * Client for the contacts API (B-01, docs/architecture/contacts.md). Organisation routes live
 * under `/api/v1/o/<org>/contacts/…`. Every call resolves (never throws on an HTTP error).
 *
 * Duplicate check (B-01-T16 client; the endpoint is B-01-T11):
 * `GET /api/v1/o/<org>/contacts/duplicates?q=<name>&email=&bn=&tax_id=&exclude=<contact id>` →
 * `{results: DuplicateMatch[]}` — the backend's `numo9.contacts.duplicates.find_duplicates()`.
 */
import { apiRequest, type ApiResult, type Numo9Error } from "@/auth/client";

/** Why a contact may be the same one: exact identifiers first, then the name. */
export type DuplicateReason = "bn" | "tax_id" | "email" | "name";

export interface DuplicateContact {
  /** Public id (UUID). */
  id: string;
  number: string;
  display_name: string;
  /** Province of the billing (else shipping) address, e.g. "ON"; "" when none. */
  province: string;
  roles: string[];
  archived: boolean;
}

export interface DuplicateMatch {
  contact: DuplicateContact;
  reasons: DuplicateReason[];
  /** Name similarity 0–1 when the name matched, else null. */
  similarity: number | null;
}

export interface DuplicateQuery {
  name?: string;
  email?: string;
  bn?: string;
  taxId?: string;
  /** The contact being edited (left out of the results). */
  exclude?: string;
}

export function duplicatesUrl(org: string, query: DuplicateQuery): string {
  const params = new URLSearchParams();
  const add = (key: string, value: string | undefined) => {
    const text = value?.trim();
    if (text) params.set(key, text);
  };
  add("q", query.name);
  add("email", query.email);
  add("bn", query.bn);
  add("tax_id", query.taxId);
  add("exclude", query.exclude);
  return `/api/v1/o/${encodeURIComponent(org)}/contacts/duplicates?${params.toString()}`;
}

export function findDuplicates(
  org: string,
  query: DuplicateQuery,
  fetcher?: typeof fetch,
): Promise<ApiResult<{ results?: DuplicateMatch[] } & Numo9Error>> {
  return apiRequest(duplicatesUrl(org, query), { fetcher });
}

/** Worth asking the server: a name of 3+ characters, an email, a 9-digit BN or a tax ID. */
export function isCheckable(query: DuplicateQuery): boolean {
  const name = (query.name ?? "").trim();
  const email = (query.email ?? "").trim();
  const bn = (query.bn ?? "").replace(/\D/g, "");
  const taxId = (query.taxId ?? "").trim();
  return name.length >= 3 || /\S+@\S+/.test(email) || bn.length >= 9 || taxId.length >= 3;
}
