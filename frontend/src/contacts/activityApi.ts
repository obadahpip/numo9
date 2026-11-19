/** Contact activity, statements and reconciliation API client (B-02-T09). */
import { apiRequest } from "@/auth/client";

export interface ActivityEventRow {
  id: string;
  type: string;
  title: string;
  amount: string | null;
  currency: string;
  occurred_at: string;
  by: string;
}

export interface StatementData {
  kind: "outstanding" | "activity";
  as_at: string;
  period_start: string | null;
  currency: string;
  contact: string;
  opening_balance: string;
  lines: {
    date: string;
    document: string;
    description: string;
    due_date: string | null;
    amount: string;
    balance: string;
  }[];
  aging: Record<string, string>;
  amount_due: string;
}

export interface SentStatement {
  id: string;
  kind: string;
  as_at: string;
  amount_due: string;
  currency: string;
  recipients: string[];
  sent_at: string;
}

export interface TheirLine {
  id: string;
  date: string;
  invoice_number: string;
  reference: string;
  description: string;
  amount: string;
  note: string;
  manual_ref: string;
}

export interface OurItem {
  ref: string;
  date: string;
  document: string;
  amount: string;
  description: string;
}

export interface Reconciliation {
  statement_date: string;
  pairs: { theirs: TheirLine; ours: OurItem; how: string; difference: string }[];
  unmatched_theirs: TheirLine[];
  unmatched_ours: OurItem[];
  their_total: string;
  our_total: string;
  difference: string;
}

const base = (org: string, id: string) =>
  `/api/v1/o/${encodeURIComponent(org)}/contacts/${encodeURIComponent(id)}`;

export interface StatementQuery {
  kind: "outstanding" | "activity";
  as_at: string;
  from?: string;
}

const query = (q: StatementQuery) =>
  new URLSearchParams(
    Object.entries(q).filter(([, v]) => Boolean(v)) as [string, string][],
  ).toString();

export const activityApi = {
  timeline: (org: string, id: string, type?: string) =>
    apiRequest<{ results: ActivityEventRow[]; types: { value: string; label: string }[] }>(
      `${base(org, id)}/activity${type ? `?type=${type}` : ""}`,
    ),
  note: (org: string, id: string, title: string) =>
    apiRequest<{ id: string }>(`${base(org, id)}/activity`, { method: "POST", body: { title } }),
  statement: (org: string, id: string, q: StatementQuery) =>
    apiRequest<StatementData>(`${base(org, id)}/statement?${query(q)}`),
  pdfUrl: (org: string, id: string, q: StatementQuery) =>
    `${base(org, id)}/statement.pdf?${query(q)}`,
  send: (org: string, id: string, q: StatementQuery) =>
    apiRequest<SentStatement>(`${base(org, id)}/statement/send`, {
      method: "POST",
      body: { kind: q.kind, as_at: q.as_at, start: q.from || null },
    }),
  history: (org: string, id: string) =>
    apiRequest<{ results: SentStatement[] }>(`${base(org, id)}/statements`),
  supplierStatements: (org: string, id: string) =>
    apiRequest<{ results: { id: string; statement_date: string; file_name: string }[] }>(
      `${base(org, id)}/supplier-statements`,
    ),
  reconciliation: (org: string, id: string, statement: string) =>
    apiRequest<Reconciliation>(`${base(org, id)}/supplier-statements/${statement}/reconciliation`),
  updateLine: (
    org: string,
    id: string,
    statement: string,
    line: string,
    change: { manual_ref?: string; note?: string },
  ) =>
    apiRequest<TheirLine>(`${base(org, id)}/supplier-statements/${statement}/lines/${line}`, {
      method: "PATCH",
      body: change,
    }),
};
