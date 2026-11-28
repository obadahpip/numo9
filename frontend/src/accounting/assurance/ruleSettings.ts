/**
 * Rule settings form logic (K-09-T23): a rule's settings as editable values, each parameter
 * validated in the browser against the rule's schema exactly as the server does it
 * (`Param.clean`: whole numbers, amounts with two decimals, minimum, maximum, choices, short
 * text, account codes), and the `PATCH assurance/rules/<code>` body of what changed. The server
 * validates again; its refusal (`assurance.param_invalid` with `param`) is shown at the field.
 */
import type { RuleChanges, RuleParam, RuleSetting, Severity } from "./api";

export type RawValue = string | boolean;

export interface RuleDraft {
  enabled: boolean;
  severity: Severity;
  values: Record<string, RawValue>;
}

export type ParamProblem =
  | { kind: "whole" | "number" | "text" | "codes" | "choice" }
  | { kind: "min"; min: string }
  | { kind: "max"; max: string };

/** A stored or default value as the field shows it. */
export function toRaw(param: RuleParam, value: unknown): RawValue {
  if (param.kind === "bool") return value === true;
  if (param.kind === "codes") return Array.isArray(value) ? value.join(", ") : "";
  return value === null || value === undefined ? "" : String(value);
}

export function draftOf(rule: RuleSetting): RuleDraft {
  return {
    enabled: rule.enabled,
    severity: rule.severity,
    values: Object.fromEntries(
      rule.params.map((p) => [
        p.name,
        toRaw(p, p.name in rule.values ? rule.values[p.name] : p.default),
      ]),
    ),
  };
}

/** The rule's defaults (Reset to defaults). */
export function defaultDraft(rule: RuleSetting): RuleDraft {
  return {
    enabled: true,
    severity: rule.default_severity,
    values: Object.fromEntries(rule.params.map((p) => [p.name, toRaw(p, p.default)])),
  };
}

const WHOLE = /^-?\d+$/;
const AMOUNT = /^-?\d+(\.\d{1,2})?$/;

type Parsed = { ok: true; value: unknown } | { ok: false; problem: ParamProblem };

/** The field's value as the API takes it, or why it can't be saved. */
export function parseParam(param: RuleParam, raw: RawValue): Parsed {
  if (param.kind === "bool") return { ok: true, value: raw === true };
  const text = String(raw).trim();
  if (param.kind === "choice") {
    return param.choices.includes(text)
      ? { ok: true, value: text }
      : { ok: false, problem: { kind: "choice" } };
  }
  if (param.kind === "str") {
    return text.length <= 100
      ? { ok: true, value: text }
      : { ok: false, problem: { kind: "text" } };
  }
  if (param.kind === "codes") {
    const codes = text
      .split(/[,\s]+/)
      .map((c) => c.trim())
      .filter(Boolean);
    return codes.every((c) => c.length <= 20)
      ? { ok: true, value: codes }
      : { ok: false, problem: { kind: "codes" } };
  }
  const pattern = param.kind === "int" ? WHOLE : AMOUNT;
  if (!pattern.test(text)) {
    return { ok: false, problem: { kind: param.kind === "int" ? "whole" : "number" } };
  }
  const number = Number(text);
  if (param.minimum !== null && number < Number(param.minimum)) {
    return { ok: false, problem: { kind: "min", min: String(param.minimum) } };
  }
  if (param.maximum !== null && number > Number(param.maximum)) {
    return { ok: false, problem: { kind: "max", max: String(param.maximum) } };
  }
  return { ok: true, value: param.kind === "int" ? number : Number(text).toFixed(2) };
}

/** Every field that can't be saved, by parameter name. */
export function problemsOf(rule: RuleSetting, draft: RuleDraft): Record<string, ParamProblem> {
  const problems: Record<string, ParamProblem> = {};
  for (const param of rule.params) {
    const parsed = parseParam(param, draft.values[param.name] ?? "");
    if (!parsed.ok) problems[param.name] = parsed.problem;
  }
  return problems;
}

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** The PATCH body of what changed against the saved settings (`null` when nothing did). */
export function changesOf(rule: RuleSetting, draft: RuleDraft): RuleChanges | null {
  const saved = draftOf(rule);
  const changes: RuleChanges = {};
  if (draft.enabled !== saved.enabled) changes.enabled = draft.enabled;
  if (draft.severity !== saved.severity) changes.severity = draft.severity;
  const params: Record<string, unknown> = {};
  for (const param of rule.params) {
    const now = parseParam(param, draft.values[param.name] ?? "");
    const before = parseParam(param, saved.values[param.name] ?? "");
    if (now.ok && !(before.ok && same(now.value, before.value))) params[param.name] = now.value;
  }
  if (Object.keys(params).length) changes.params = params;
  return Object.keys(changes).length ? changes : null;
}
