/**
 * The builder's working copy of a rule (F-04-T11…T14) and its conversions: from a saved rule,
 * from pre-fill query parameters ("Create rule from line", T14) and to the API's input.
 */
import type {
  AllocationInput,
  BankRule,
  ContactStrategy,
  MatchMode,
  RuleCondition,
  RuleInput,
  RuleType,
} from "./api";

export interface AllocationRow {
  account: string;
  tax_code: string;
  description: string;
  mode: "percent" | "fixed";
  value: string;
}

export interface RuleDraft {
  type: RuleType;
  name: string;
  match_mode: MatchMode;
  conditions: RuleCondition[];
  allocations: AllocationRow[];
  contact_strategy: ContactStrategy;
  contact: string | null;
  reference_template: string;
  transfer_account: string | null;
  scope_accounts: string[];
  auto_apply: boolean;
  active: boolean;
}

export function emptyAllocation(): AllocationRow {
  return { account: "", tax_code: "", description: "", mode: "percent", value: "100" };
}

export function newDraft(type: RuleType = "spend"): RuleDraft {
  return {
    type,
    name: "",
    match_mode: "all",
    conditions: [{ field: "description", operator: "contains", value: "", value_to: "" }],
    allocations: type === "transfer" ? [] : [emptyAllocation()],
    contact_strategy: "none",
    contact: null,
    reference_template: "",
    transfer_account: null,
    scope_accounts: [],
    auto_apply: false,
    active: true,
  };
}

export function draftOf(rule: BankRule): RuleDraft {
  return {
    type: rule.type,
    name: rule.name,
    match_mode: rule.match_mode,
    conditions: rule.conditions.map((c) => ({ ...c })),
    allocations: rule.allocations.map((a) => ({
      account: a.account.id,
      tax_code: a.tax_code,
      description: a.description,
      mode: a.percent !== null ? "percent" : "fixed",
      value: (a.percent ?? a.fixed_amount ?? "").toString(),
    })),
    contact_strategy: rule.contact_strategy,
    contact: rule.contact?.id ?? null,
    reference_template: rule.reference_template,
    transfer_account: rule.transfer_account?.id ?? null,
    scope_accounts: rule.scope_accounts.map((a) => a.id),
    auto_apply: rule.auto_apply,
    active: rule.active,
  };
}

function allocationInput(row: AllocationRow): AllocationInput {
  return {
    account: row.account,
    tax_code: row.tax_code,
    description: row.description,
    fixed_amount: row.mode === "fixed" ? row.value.trim() : null,
    percent: row.mode === "percent" ? row.value.trim() : null,
  };
}

export function toInput(draft: RuleDraft): RuleInput {
  const transfer = draft.type === "transfer";
  return {
    type: draft.type,
    name: draft.name.trim(),
    match_mode: draft.match_mode,
    conditions: draft.conditions.map((c) => ({
      ...c,
      value_to: c.operator === "between" ? c.value_to : "",
      value: c.operator === "is_blank" ? "" : c.value,
    })),
    allocations: transfer ? [] : draft.allocations.map(allocationInput),
    scope_accounts: draft.scope_accounts,
    contact_strategy: draft.contact_strategy,
    contact: draft.contact_strategy === "fixed" ? draft.contact : null,
    reference_template: draft.reference_template,
    transfer_account: transfer ? draft.transfer_account : null,
    auto_apply: draft.auto_apply,
    active: draft.active,
  };
}
