/**
 * Find & recode condition builder model (C-07-T10): the fields and operators the search accepts
 * (backend `numo9/ledger/recode_query.py`), the typed value each needs, and `serialise()` from
 * the builder's rows to the API schema `{match, conditions: [{field, op, value}]}`.
 *
 * A row is complete when its value is (`emptyRows` lists the ones that aren't); `in` values are
 * comma-separated in a text box and sent as a list; ranges are `{from, to}`; tracking is
 * `{category: option}`; `empty` takes no value.
 */
import type { Condition, Criteria, Match } from "./api";

export type FieldKey =
  | "type"
  | "status"
  | "account"
  | "bank_account"
  | "date"
  | "amount"
  | "tax_code"
  | "entered_by"
  | "contact"
  | "number"
  | "reference"
  | "tracking"
  | "book";

/** How the row's value is entered. */
export type InputKind = "choice" | "account" | "date" | "amount" | "text" | "tracking" | "none";

export interface FieldSpec {
  ops: string[];
  input: (op: string) => InputKind;
  /** The fixed values of a `choice` field. */
  choices?: string[];
}

const single =
  (kind: InputKind) =>
  (op: string): InputKind =>
    op === "empty" ? "none" : kind;

export const ENTRY_TYPES = [
  "manual",
  "sales",
  "purchase",
  "payment",
  "payroll",
  "opening",
  "adjustment",
  "bank",
];

export const FIELDS: Record<FieldKey, FieldSpec> = {
  type: { ops: ["is"], input: () => "choice", choices: ENTRY_TYPES },
  status: { ops: ["is"], input: () => "choice", choices: ["posted", "reversed"] },
  account: { ops: ["is", "not"], input: () => "account" },
  bank_account: { ops: ["is"], input: () => "account" },
  date: { ops: ["on", "before", "after", "between"], input: () => "date" },
  amount: { ops: ["eq", "gt", "gte", "lt", "lte", "between"], input: () => "amount" },
  tax_code: { ops: ["is", "in", "empty"], input: single("text") },
  entered_by: { ops: ["is"], input: () => "text" },
  contact: { ops: ["is", "empty"], input: single("text") },
  number: { ops: ["is"], input: () => "text" },
  reference: { ops: ["contains"], input: () => "text" },
  tracking: { ops: ["is"], input: () => "tracking" },
  book: { ops: ["is"], input: () => "choice", choices: ["both", "accounting", "tax"] },
};

export const FIELD_KEYS = Object.keys(FIELDS) as FieldKey[];

/** One row of the builder: `value` / `value2` (a range's end, a tracking option). */
export interface Row {
  id: string;
  field: FieldKey;
  op: string;
  value: string;
  value2: string;
}

let counter = 0;

export function newRow(field: FieldKey = "account"): Row {
  counter += 1;
  const spec = FIELDS[field];
  return {
    id: `c${counter}`,
    field,
    op: spec.ops[0] ?? "is",
    value: spec.choices?.[0] ?? "",
    value2: "",
  };
}

/** A row moved to another field starts from that field's first operator and an empty value. */
export function withField(row: Row, field: FieldKey): Row {
  const spec = FIELDS[field];
  return { ...row, field, op: spec.ops[0] ?? "is", value: spec.choices?.[0] ?? "", value2: "" };
}

const isRange = (row: Row) => row.op === "between";

export function isComplete(row: Row): boolean {
  const kind = FIELDS[row.field].input(row.op);
  if (kind === "none") return true;
  if (kind === "tracking") return row.value.trim() !== "" && row.value2.trim() !== "";
  if (isRange(row)) return row.value.trim() !== "" && row.value2.trim() !== "";
  if (kind === "amount") return row.value.trim() !== "" && Number.isFinite(Number(row.value));
  return row.value.trim() !== "";
}

export function emptyRows(rows: Row[]): string[] {
  return rows.filter((row) => !isComplete(row)).map((row) => row.id);
}

function valueOf(row: Row): unknown {
  const kind = FIELDS[row.field].input(row.op);
  if (kind === "none") return null;
  if (kind === "tracking") return { [row.value.trim()]: row.value2.trim() };
  if (isRange(row)) return { from: row.value.trim(), to: row.value2.trim() };
  if (row.op === "in") {
    return row.value
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
  }
  return row.value.trim();
}

export function toCondition(row: Row): Condition {
  return { field: row.field, op: row.op, value: valueOf(row) };
}

/** The builder's rows as the API's search; incomplete rows are left out. */
export function serialise(match: Match, rows: Row[]): Criteria {
  return { match, conditions: rows.filter(isComplete).map(toCondition) };
}
