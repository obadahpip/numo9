/**
 * Client for the audit log API (A-04-T07…T11, docs/architecture/audit.md § API):
 * `/api/v1/o/<org>/audit/…`. Every call resolves (never throws on an HTTP error): screens branch
 * on `status` and the error `code` (`permission.denied` → the "why can't I?" panel).
 */
import { apiRequest, type ApiResult, type Numo9Error } from "@/auth/client";

export type ActorKind = "user" | "system" | "impersonation";
export type Verb = "created" | "updated" | "deleted" | "restored" | "other";

export interface AuditPerson {
  id: string;
  name: string;
  email: string;
}

/** A value in a change: text, number, null, or a marker object. */
export type AuditValue =
  | string
  | number
  | boolean
  | null
  | { masked: true }
  | { truncated: true; text: string; length: number }
  | { id: string; label: string }
  | Record<string, unknown>
  | unknown[];

export interface AuditChange {
  field: string;
  label: string;
  old: AuditValue;
  new: AuditValue;
  /** The value is hidden (SIN, bank details…): the field changed, nothing more. */
  masked: boolean;
}

export interface AuditEvent {
  id: string;
  /** ISO date-time (UTC offset). */
  at: string;
  action: string;
  action_label: string;
  verb: Verb;
  actor: {
    kind: ActorKind;
    label: string;
    user: AuditPerson | null;
    impersonator: AuditPerson | null;
  };
  record: { type: string; type_label: string; id: string; label: string };
  changes: AuditChange[];
  meta: Record<string, unknown>;
  ip: string | null;
  device: string;
  request_id: string;
  batch_id: string | null;
  is_batch_summary: boolean;
}

/** The viewer's display preferences, sent with every list (A-04-T12). */
export interface AuditViewer {
  locale: string;
  time_format: "12h" | "24h";
  time_zone: string;
}

export interface AuditPage {
  results: AuditEvent[];
  next: string | null;
  range: { from: string; to: string; default: boolean; time_zone: string };
  viewer: AuditViewer;
}

export interface AuditHistory {
  record: AuditEvent["record"];
  results: AuditEvent[];
  next: string | null;
  viewer: AuditViewer;
}

export interface AuditOption {
  value: string;
  label: string;
}

export interface AuditFilterChoices {
  users: AuditOption[];
  types: AuditOption[];
  actions: AuditOption[];
}

/** Filters of the global viewer (the API's query parameters). */
export interface AuditFilters {
  from?: string;
  to?: string;
  user?: string;
  type?: string[];
  action?: string;
  q?: string;
  batch?: string;
  /** One record (links from the record history drawer). */
  object_type?: string;
  object_id?: string;
}

export type AuditError = Numo9Error;
export type ExportFormat = "csv" | "xlsx" | "pdf";
export const EXPORT_FORMATS: ExportFormat[] = ["csv", "xlsx", "pdf"];

export function auditApi(org: string, path: string): string {
  return `/api/v1/o/${encodeURIComponent(org)}/audit/${path}`;
}

/** Query string of the filters: the same for the list and the exports (export = screen). */
export function filterParams(filters: AuditFilters): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of [
    "from",
    "to",
    "user",
    "action",
    "q",
    "batch",
    "object_type",
    "object_id",
  ] as const) {
    const value = filters[key];
    if (value) params.set(key, value);
  }
  for (const type of filters.type ?? []) params.append("type", type);
  return params;
}

export function listEvents(
  org: string,
  filters: AuditFilters,
  cursor?: string | null,
): Promise<ApiResult<AuditPage | AuditError>> {
  const params = filterParams(filters);
  if (cursor) params.set("cursor", cursor);
  return apiRequest<AuditPage | AuditError>(`${auditApi(org, "events")}?${params.toString()}`);
}

export function getEvent(org: string, id: string): Promise<ApiResult<AuditEvent | AuditError>> {
  return apiRequest<AuditEvent | AuditError>(auditApi(org, `events/${encodeURIComponent(id)}`));
}

export function getFilterChoices(org: string): Promise<ApiResult<AuditFilterChoices | AuditError>> {
  return apiRequest<AuditFilterChoices | AuditError>(auditApi(org, "filters"));
}

export function recordHistory(
  org: string,
  type: string,
  id: string,
  cursor?: string | null,
): Promise<ApiResult<AuditHistory | AuditError>> {
  const path = `records/${encodeURIComponent(type)}/${encodeURIComponent(id)}`;
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return apiRequest<AuditHistory | AuditError>(`${auditApi(org, path)}${query}`);
}

export interface AuditAsOf {
  record: AuditEvent["record"];
  at: string;
  /** Created by then and not deleted. */
  exists: boolean;
  deleted: boolean;
  /** The history starts at the record's creation (every field known). */
  complete: boolean;
  events_applied: number;
  last_event: AuditEvent | null;
  state: { field: string; label: string; value: AuditValue; masked: boolean }[];
  viewer: AuditViewer;
}

/** A record's fields as they were at `at` (a date: the end of that day), A-04-T11. */
export function recordAsOf(
  org: string,
  type: string,
  id: string,
  at: string,
): Promise<ApiResult<AuditAsOf | AuditError>> {
  const path = `records/${encodeURIComponent(type)}/${encodeURIComponent(id)}/as-of`;
  return apiRequest<AuditAsOf | AuditError>(`${auditApi(org, path)}?at=${encodeURIComponent(at)}`);
}

/** Download link of an export with the screen's filters (same-origin: the session cookie). */
export function exportUrl(org: string, format: ExportFormat, filters: AuditFilters): string {
  const query = filterParams(filters).toString();
  return `${auditApi(org, `export/${format}`)}${query ? `?${query}` : ""}`;
}

export const isAuditError = (body: unknown): body is AuditError =>
  typeof body === "object" && body !== null && "code" in body && "detail" in body;
