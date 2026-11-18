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

// ---- contacts list, form and merge (B-01-T14, T15, T17; API B-01-T11, T12) -------------------

export type ContactRoleKey =
  "customer" | "supplier" | "employee" | "contractor" | "government_agency";

export interface ContactSummary {
  id: string;
  number: string;
  display_name: string;
  legal_name: string;
  roles: ContactRoleKey[];
  email: string;
  phone: string;
  person: string;
  province: string;
  city: string;
  currency: string;
  bn: string;
  status: "active" | "archived";
}

export interface ContactPersonRow {
  id?: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  job_title: string;
  is_primary: boolean;
  include_in_emails: boolean;
}

export interface AddressRow {
  id?: string;
  kind: "billing" | "shipping";
  attention: string;
  line1: string;
  line2: string;
  city: string;
  province: string;
  region: string;
  postal_code: string;
  country: string;
}

export interface ContactDetail extends ContactSummary {
  tax_id: string;
  credit_limit: string | null;
  credit_mode: "warn" | "block";
  t4a_flag: boolean;
  portal_enabled: boolean;
  statement_pref: string;
  language: string;
  sales_account: { id: string; code: string; name: string } | null;
  purchase_account: { id: string; code: string; name: string } | null;
  sales_amounts_are: string;
  purchase_amounts_are: string;
  people: ContactPersonRow[];
  addresses: AddressRow[];
  merged_into: { id: string; name: string } | null;
}

export interface ContactWrite {
  display_name?: string;
  legal_name?: string;
  roles?: ContactRoleKey[];
  bn?: string;
  tax_id?: string;
  currency?: string;
  credit_limit?: string | null;
  credit_mode?: "warn" | "block";
  sales_account?: string | null;
  purchase_account?: string | null;
  people?: ContactPersonRow[];
  addresses?: AddressRow[];
}

export interface ContactPage {
  results: ContactSummary[];
  count: number;
  next_offset: number | null;
  role_counts: Record<ContactRoleKey, number>;
}

export interface MergeRecords {
  records: string;
  count: number;
  moves: boolean;
}

const contactsBase = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/contacts`;

export const contactsApi = {
  list: (org: string, params: { role?: string; status?: string; q?: string }) => {
    const query = new URLSearchParams({ limit: "200" });
    for (const [key, value] of Object.entries(params)) if (value) query.set(key, value);
    return apiRequest<ContactPage>(`${contactsBase(org)}?${query.toString()}`);
  },
  get: (org: string, id: string) => apiRequest<ContactDetail>(`${contactsBase(org)}/${id}`),
  create: (org: string, body: ContactWrite) =>
    apiRequest<ContactDetail>(contactsBase(org), { method: "POST", body }),
  update: (org: string, id: string, body: ContactWrite) =>
    apiRequest<ContactDetail>(`${contactsBase(org)}/${id}`, { method: "PATCH", body }),
  archive: (org: string, id: string) =>
    apiRequest<ContactDetail>(`${contactsBase(org)}/${id}/archive`, { method: "POST" }),
  restore: (org: string, id: string) =>
    apiRequest<ContactDetail>(`${contactsBase(org)}/${id}/restore`, { method: "POST" }),
  mergePreview: (org: string, survivor: string, merged: string) =>
    apiRequest<{ survivor: ContactDetail; merged: ContactDetail; records: MergeRecords[] }>(
      `${contactsBase(org)}/merge/preview?survivor=${survivor}&merged=${merged}`,
    ),
  merge: (org: string, survivor: string, merged: string, fieldSources: Record<string, string>) =>
    apiRequest<{ survivor: ContactDetail }>(`${contactsBase(org)}/merge`, {
      method: "POST",
      body: { survivor, merged, field_sources: fieldSources },
    }),
};

/** First readable message of a refusal: `{detail}`, `{field: [msg]}` or `{non_field_errors}`. */
export function firstError(body: unknown): string | undefined {
  if (!body || typeof body !== "object") return undefined;
  const record = body as Record<string, unknown>;
  if (typeof record.detail === "string") return record.detail;
  for (const value of Object.values(record)) {
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  }
  return undefined;
}

/** Field errors keyed like the API: `display_name`, `addresses[0].postal_code`. */
export function fieldErrors(body: unknown): Record<string, string> {
  const found: Record<string, string> = {};
  if (!body || typeof body !== "object") return found;
  for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
    if (Array.isArray(value) && typeof value[0] === "string") found[key] = value[0];
  }
  return found;
}
