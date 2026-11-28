/**
 * Bank rules API client (F-04-T09): `/api/v1/o/<org>/bank-rules…` — list, CRUD, atomic reorder,
 * history preview, apply. Rules are ordered per type (spend / receive / transfer); the first
 * matching rule wins.
 */
import { apiRequest, type ApiResult } from "@/auth/client";

export type RuleType = "spend" | "receive" | "transfer";
export const RULE_TYPES: readonly RuleType[] = ["spend", "receive", "transfer"];

export type ConditionField = "payee" | "description" | "reference" | "any_text" | "amount";
export type ConditionOperator =
  | "equals"
  | "contains"
  | "not_contains"
  | "starts_with"
  | "ends_with"
  | "regex"
  | "is_blank"
  | "between"
  | "gt"
  | "lt";

export const TEXT_FIELDS: readonly ConditionField[] = [
  "payee",
  "description",
  "reference",
  "any_text",
];
export const CONDITION_FIELDS: readonly ConditionField[] = [...TEXT_FIELDS, "amount"];
export const TEXT_OPERATORS: readonly ConditionOperator[] = [
  "contains",
  "not_contains",
  "equals",
  "starts_with",
  "ends_with",
  "regex",
  "is_blank",
];
export const AMOUNT_OPERATORS: readonly ConditionOperator[] = ["between", "equals", "gt", "lt"];

export function operatorsFor(field: ConditionField): readonly ConditionOperator[] {
  return field === "amount" ? AMOUNT_OPERATORS : TEXT_OPERATORS;
}

export type ContactStrategy = "none" | "fixed" | "match_payee";
export type MatchMode = "all" | "any";

export interface RuleCondition {
  field: ConditionField;
  operator: ConditionOperator;
  value: string;
  value_to: string;
}

export interface RuleAllocation {
  account: { id: string; code: string; name: string };
  tax_code: string;
  description: string;
  fixed_amount: string | null;
  percent: string | null;
}

export interface BankRule {
  id: string;
  type: RuleType;
  name: string;
  match_mode: MatchMode;
  priority: number | null;
  active: boolean;
  auto_apply: boolean;
  contact_strategy: ContactStrategy;
  contact: { id: string; name: string } | null;
  reference_template: string;
  transfer_account: { id: string; name: string } | null;
  scope_accounts: { id: string; name: string }[];
  conditions: RuleCondition[];
  allocations: RuleAllocation[];
  applied_count: number;
  last_applied_at: string | null;
  /** Why the rule is disabled: `archived_account`, `archived_bank_account`. */
  warnings: string[];
}

export interface AllocationInput {
  account: string;
  tax_code?: string;
  description?: string;
  fixed_amount?: string | null;
  percent?: string | null;
}

export interface RuleInput {
  type: RuleType;
  name: string;
  match_mode: MatchMode;
  conditions: RuleCondition[];
  allocations: AllocationInput[];
  scope_accounts?: string[];
  contact_strategy?: ContactStrategy;
  contact?: string | null;
  reference_template?: string;
  transfer_account?: string | null;
  auto_apply?: boolean;
  active?: boolean;
}

export interface RuleRefusal {
  code?: string;
  detail?: string;
  field?: string;
}

export interface PreviewLine {
  id: string;
  date: string;
  amount: string;
  payee: string;
  description: string;
  reference: string;
  bank_account: { id: string; name: string };
}

export interface PreviewRow {
  line: PreviewLine;
  outcome: "applies" | "shadowed";
  shadowed_by: { id: string | null; name: string } | null;
  also_matches: { id: string | null; name: string }[];
}

export interface PreviewResult {
  since: string;
  days: number;
  applies: number;
  shadowed: number;
  truncated: boolean;
  rows: PreviewRow[];
}

export interface RuleFilters {
  type?: RuleType;
  status?: "active" | "inactive" | "all";
  search?: string;
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/bank-rules`;

export function rulesQuery(filters: RuleFilters): string {
  const params = new URLSearchParams(
    Object.entries(filters).filter((entry): entry is [string, string] => Boolean(entry[1])),
  );
  const text = params.toString();
  return text ? `?${text}` : "";
}

export const rulesApi = {
  list: (org: string, filters: RuleFilters = {}): Promise<ApiResult<{ results: BankRule[] }>> =>
    apiRequest(`${base(org)}${rulesQuery(filters)}`),
  get: (org: string, id: string): Promise<ApiResult<BankRule>> => apiRequest(`${base(org)}/${id}`),
  create: (org: string, body: RuleInput): Promise<ApiResult<BankRule & RuleRefusal>> =>
    apiRequest(base(org), { method: "POST", body }),
  update: (
    org: string,
    id: string,
    body: Partial<RuleInput>,
  ): Promise<ApiResult<BankRule & RuleRefusal>> =>
    apiRequest(`${base(org)}/${id}`, { method: "PATCH", body }),
  remove: (org: string, id: string): Promise<ApiResult<RuleRefusal>> =>
    apiRequest(`${base(org)}/${id}`, { method: "DELETE" }),
  reorder: (
    org: string,
    type: RuleType,
    order: string[],
  ): Promise<ApiResult<{ results: BankRule[] } & RuleRefusal>> =>
    apiRequest(`${base(org)}/reorder`, { method: "POST", body: { type, order } }),
  preview: (
    org: string,
    rule: RuleInput,
    options: { id?: string | null; days?: number } = {},
  ): Promise<ApiResult<PreviewResult & RuleRefusal>> =>
    apiRequest(`${base(org)}/preview`, {
      method: "POST",
      body: { rule, id: options.id ?? null, days: options.days ?? null },
    }),
};

/** `/o/:org/banking/rules` — the rules list (F-04-T10). */
export function rulesUrl(org: string, type?: RuleType): string {
  return `/o/${org}/banking/rules${type && type !== "spend" ? `?type=${type}` : ""}`;
}

/** The builder: a new rule (optionally pre-filled, F-04-T14) or an existing one. */
export function ruleUrl(org: string, id?: string): string {
  return id ? `/o/${org}/banking/rules/${id}` : `/o/${org}/banking/rules/new`;
}
