/**
 * Assurance API client (K-09-T20): `/api/v1/o/<org>/assurance/` — summary, findings, workflow
 * (acknowledge, false positive, reopen), proposed fix and its draft, run, rules, heatmap.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export type Severity = "critical" | "warning" | "info";
export type FindingStatus = "open" | "acknowledged" | "resolved" | "false_positive";

export interface Summary {
  score: number;
  open: Record<Severity, number>;
  statuses: Record<FindingStatus, number>;
  attention: number;
  rules: { rule: string; name: string; severity: Severity; count: number }[];
  last_run: { id: string; trigger: string; started_at: string; finished_at: string | null } | null;
}

export interface Finding {
  id: string;
  rule: string;
  rule_name: string;
  severity: Severity;
  status: FindingStatus;
  subject: { type: string; id: string; label: string };
  amount: string | null;
  details: Record<string, unknown>;
  explanation: string;
  has_fix: boolean;
  source: { kind: string; path: string } | null;
  first_seen: string;
  last_seen: string;
  resolved_at: string | null;
  ack_by: { id: string; name: string } | null;
  ack_at: string | null;
  reason: string;
  fix_entry: string | null;
}

export interface FixLine {
  account: string;
  code: string;
  label: string;
  debit: string;
  credit: string;
  description: string;
}

export interface Fix {
  kind: "journal" | "recode";
  reasoning: string;
  date: string | null;
  narration: string;
  lines: FixLine[];
  recode: { criteria: unknown; changes: Record<string, string> } | null;
  alternatives: Fix[];
}

export interface FindingQuery {
  severity?: Severity[];
  status?: FindingStatus[];
  q?: string;
}

type Result<T> = Promise<ApiResult<T & { detail?: string; code?: string }>>;

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/assurance`;
const finding = (org: string, id: string) => `${base(org)}/findings/${encodeURIComponent(id)}`;

export function findingsUrl(org: string, query: FindingQuery = {}): string {
  const params = new URLSearchParams();
  for (const s of query.severity ?? []) params.append("severity", s);
  for (const s of query.status ?? []) params.append("status", s);
  if (query.q?.trim()) params.set("q", query.q.trim());
  const text = params.toString();
  return `${base(org)}/findings${text ? `?${text}` : ""}`;
}

export const assuranceApi = {
  summary: (org: string): Result<Summary> => apiRequest(`${base(org)}/`),
  findings: (
    org: string,
    query: FindingQuery = {},
  ): Result<{ count: number; findings: Finding[] }> => apiRequest(findingsUrl(org, query)),
  acknowledge: (org: string, id: string, reason = ""): Result<Finding> =>
    apiRequest(`${finding(org, id)}/acknowledge`, { method: "POST", body: { reason } }),
  falsePositive: (org: string, id: string, reason: string): Result<Finding> =>
    apiRequest(`${finding(org, id)}/false-positive`, { method: "POST", body: { reason } }),
  reopen: (org: string, id: string): Result<Finding> =>
    apiRequest(`${finding(org, id)}/reopen`, { method: "POST", body: {} }),
  fix: (org: string, id: string): Result<{ fix: Fix | null }> =>
    apiRequest(`${finding(org, id)}/fix`),
  createFix: (
    org: string,
    id: string,
    body: {
      lines?: Pick<FixLine, "account" | "debit" | "credit" | "description">[];
      date?: string;
      narration?: string;
    } = {},
  ): Result<{ draft: { id: string; status: string }; finding: Finding }> =>
    apiRequest(`${finding(org, id)}/fix`, { method: "POST", body }),
  run: (org: string): Result<{ job: string }> =>
    apiRequest(`${base(org)}/run`, { method: "POST", body: {} }),
};
