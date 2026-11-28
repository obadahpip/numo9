/**
 * Assurance API client (K-09-T20): `/api/v1/o/<org>/assurance/` — summary, findings, workflow
 * (acknowledge, false positive, reopen), proposed fix and its draft, run, rule settings
 * (K-09-T23), heatmap (K-09-T24).
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

export type ParamKind = "int" | "decimal" | "bool" | "choice" | "str" | "codes";

/** One parameter of a rule's schema (K-09-T04 `Param.as_dict`). */
export interface RuleParam {
  name: string;
  kind: ParamKind;
  label: string;
  default: unknown;
  minimum: number | string | null;
  maximum: number | string | null;
  choices: string[];
}

/** A rule with its schema and the organisation's settings (`GET assurance/rules`). */
export interface RuleSetting {
  code: string;
  name: string;
  description: string;
  default_severity: Severity;
  incremental: boolean;
  has_fix: boolean;
  params: RuleParam[];
  enabled: boolean;
  severity: Severity;
  values: Record<string, unknown>;
}

export interface RuleChanges {
  enabled?: boolean;
  severity?: Severity;
  params?: Record<string, unknown>;
}

/** User activity per day and person from the audit log (`GET assurance/heatmap`, K-09-T19). */
export interface Heatmap {
  from: string;
  to: string;
  time_zone: string;
  total: number;
  days: { date: string; count: number }[];
  people: { id: string; name: string; count: number; last: string | null }[];
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
  rules: (org: string): Result<{ rules: RuleSetting[] }> => apiRequest(`${base(org)}/rules`),
  updateRule: (
    org: string,
    code: string,
    changes: RuleChanges,
  ): Result<RuleSetting & { param?: string }> =>
    apiRequest(`${base(org)}/rules/${encodeURIComponent(code)}`, {
      method: "PATCH",
      body: changes,
    }),
  heatmap: (org: string, { days = 365, user = "" }: { days?: number; user?: string } = {}) => {
    const params = new URLSearchParams({ days: String(days) });
    if (user) params.set("user", user);
    return apiRequest<Heatmap & { detail?: string }>(`${base(org)}/heatmap?${params.toString()}`);
  },
  run: (org: string): Result<{ job: string }> =>
    apiRequest(`${base(org)}/run`, { method: "POST", body: {} }),
};
