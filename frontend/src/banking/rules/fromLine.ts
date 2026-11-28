/**
 * "Create rule from this line" (F-04-T14): the link a statement line carries to the rule
 * builder, and the builder's pre-fill read back from its query.
 *
 * `/o/:org/banking/rules/new?from_line=<id>&type=spend&payee=…&description=…&bank_account=…`
 * opens a new rule of the line's type (money out → spend, money in → receive), named after the
 * payee (or the description), with one condition: **Payee contains** the payee when the line has
 * one, otherwise **Description contains** the description without its store / reference numbers
 * ("PETRO-CANADA #1234 TORONTO" → "PETRO-CANADA TORONTO"), scoped to the line's bank account.
 */
import type { RuleType } from "./api";
import { newDraft, type RuleDraft } from "./draft";

/** What the action needs from a statement line (the F-02 list's row has these fields). */
export interface StatementLineLike {
  id?: string;
  amount: string | number;
  payee?: string;
  description?: string;
  bank_account?: string | { id: string } | null;
}

const MAX = 120;

/** The description without reference numbers: "#1234", "000123", "REF 9876" are dropped. */
export function keywordOf(description: string): string {
  return description
    .replace(/#\s*\d+/g, " ")
    .replace(/\b(?:ref|no|n°)\.?\s*\d+/gi, " ")
    .replace(/\b\d{3,}\b/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, MAX);
}

export function lineType(amount: string | number): RuleType {
  return Number(amount) > 0 ? "receive" : "spend";
}

export function ruleFromLineHref(org: string, line: StatementLineLike): string {
  const bank = typeof line.bank_account === "string" ? line.bank_account : line.bank_account?.id;
  const params = new URLSearchParams();
  if (line.id) params.set("from_line", line.id);
  params.set("type", lineType(line.amount));
  if (line.payee?.trim()) params.set("payee", line.payee.trim().slice(0, MAX));
  if (line.description?.trim()) params.set("description", line.description.trim().slice(0, 500));
  if (bank) params.set("bank_account", bank);
  return `/o/${org}/banking/rules/new?${params.toString()}`;
}

type Query = Record<string, string | string[] | undefined>;

function one(query: Query, key: string): string {
  const value = query[key];
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

/** Is this a pre-filled "new rule" query? */
export function hasPrefill(query: Query): boolean {
  return Boolean(one(query, "payee") || one(query, "description") || one(query, "from_line"));
}

export function prefillDraft(query: Query): RuleDraft {
  const wanted = one(query, "type");
  const type: RuleType = wanted === "receive" || wanted === "transfer" ? wanted : "spend";
  const draft = newDraft(type);
  const payee = one(query, "payee");
  const keyword = keywordOf(one(query, "description"));
  const bank = one(query, "bank_account");
  if (payee) {
    draft.conditions = [{ field: "payee", operator: "contains", value: payee, value_to: "" }];
  } else if (keyword) {
    draft.conditions = [
      { field: "description", operator: "contains", value: keyword, value_to: "" },
    ];
  }
  draft.name = (payee || keyword).slice(0, MAX);
  if (bank) draft.scope_accounts = [bank];
  return draft;
}
