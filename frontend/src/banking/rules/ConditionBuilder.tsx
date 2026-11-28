"use client";

/**
 * Sentence-style condition builder (F-04-T11): "When [all ▾] of these are true: [Description ▾]
 * [contains ▾] [PETRO] and [Amount ▾] [is between ▾] [20] and [200]". Inputs follow the
 * operator: **amount between** shows two amount fields, **is blank** none, **regex** a pattern
 * field with a tester that highlights the matches in a sample text (case and accents ignored).
 * Changing the field keeps the operator when it still applies, otherwise picks the first one.
 */
import { Button, INPUT_BASE, Input } from "@numo9/ui";
import { useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import {
  CONDITION_FIELDS,
  operatorsFor,
  type ConditionField,
  type ConditionOperator,
  type MatchMode,
  type RuleCondition,
} from "./api";
import { builder } from "./builderMessages";
import { fieldLabels, m, operatorLabels } from "./messages";
import { highlightMatches } from "./regex";

export function emptyCondition(field: ConditionField = "description"): RuleCondition {
  return { field, operator: field === "amount" ? "between" : "contains", value: "", value_to: "" };
}

/** Is the condition complete enough to save or preview? */
export function conditionComplete(condition: RuleCondition): boolean {
  if (condition.operator === "is_blank") return true;
  if (!condition.value.trim()) return false;
  if (condition.field === "amount") {
    const low = Number(condition.value);
    if (!Number.isFinite(low) || low < 0) return false;
    if (condition.operator === "between") {
      const high = Number(condition.value_to);
      return condition.value_to.trim() !== "" && Number.isFinite(high) && high >= low;
    }
  }
  if (condition.operator === "regex") return !highlightMatches(condition.value, "").error;
  return true;
}

export interface ConditionBuilderProps {
  conditions: RuleCondition[];
  matchMode: MatchMode;
  onChange: (conditions: RuleCondition[]) => void;
  onMatchModeChange: (mode: MatchMode) => void;
}

const SELECT = `${INPUT_BASE} w-auto`;

export function ConditionBuilder({
  conditions,
  matchMode,
  onChange,
  onMatchModeChange,
}: ConditionBuilderProps) {
  const fm = useFormatMessage();
  const id = useId();

  function update(index: number, changes: Partial<RuleCondition>) {
    onChange(conditions.map((c, i) => (i === index ? { ...c, ...changes } : c)));
  }

  function setField(index: number, field: ConditionField) {
    const current = conditions[index]!;
    const allowed = operatorsFor(field);
    const operator = allowed.includes(current.operator) ? current.operator : allowed[0]!;
    update(index, { field, operator, value_to: operator === "between" ? current.value_to : "" });
  }

  return (
    <fieldset className="flex flex-col gap-4" aria-labelledby={`${id}-legend`}>
      <legend id={`${id}-legend`} className="sr-only">
        {fm(builder.conditionsLegend)}
      </legend>
      <p className="flex flex-wrap items-center gap-2 text-base text-fg">
        <span>{fm(builder.when)}</span>
        <select
          aria-label={fm(builder.matchMode)}
          className={SELECT}
          value={matchMode}
          onChange={(e) => onMatchModeChange(e.target.value as MatchMode)}
        >
          <option value="all">{fm(builder.matchAll)}</option>
          <option value="any">{fm(builder.matchAny)}</option>
        </select>
        <span>{fm(builder.ofThese)}</span>
      </p>
      <ol className="flex flex-col gap-3">
        {conditions.map((condition, index) => (
          <ConditionRow
            key={index}
            index={index}
            condition={condition}
            joiner={index === 0 ? "" : fm(matchMode === "any" ? m.or : m.and)}
            onField={(field) => setField(index, field)}
            onChange={(changes) => update(index, changes)}
            onRemove={
              conditions.length > 1
                ? () => onChange(conditions.filter((_c, i) => i !== index))
                : undefined
            }
          />
        ))}
      </ol>
      <div>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => onChange([...conditions, emptyCondition()])}
        >
          {fm(builder.addCondition)}
        </Button>
      </div>
    </fieldset>
  );
}

function ConditionRow({
  index,
  condition,
  joiner,
  onField,
  onChange,
  onRemove,
}: {
  index: number;
  condition: RuleCondition;
  joiner: string;
  onField: (field: ConditionField) => void;
  onChange: (changes: Partial<RuleCondition>) => void;
  onRemove?: () => void;
}) {
  const fm = useFormatMessage();
  const number = index + 1;
  const isAmount = condition.field === "amount";
  return (
    <li className="flex flex-col gap-2 rounded-lg border border-border p-3" data-condition={index}>
      <div className="flex flex-wrap items-center gap-2">
        {joiner ? <span className="text-sm font-semibold text-fg-muted">{joiner}</span> : null}
        <select
          aria-label={fm(builder.fieldLabel, { number })}
          className={SELECT}
          value={condition.field}
          onChange={(e) => onField(e.target.value as ConditionField)}
        >
          {CONDITION_FIELDS.map((f) => (
            <option key={f} value={f}>
              {fm(fieldLabels[f])}
            </option>
          ))}
        </select>
        <select
          aria-label={fm(builder.operatorLabel, { number })}
          className={SELECT}
          value={condition.operator}
          onChange={(e) => onChange({ operator: e.target.value as ConditionOperator })}
        >
          {operatorsFor(condition.field).map((o) => (
            <option key={o} value={o}>
              {fm(operatorLabels[o])}
            </option>
          ))}
        </select>
        {condition.operator === "is_blank" ? null : condition.operator === "between" ? (
          <>
            <Input
              aria-label={fm(builder.amountFrom, { number })}
              inputMode="decimal"
              numeric
              className="w-28"
              value={condition.value}
              onChange={(e) => onChange({ value: e.target.value })}
            />
            <span className="text-sm text-fg">{fm(m.and)}</span>
            <Input
              aria-label={fm(builder.amountTo, { number })}
              inputMode="decimal"
              numeric
              className="w-28"
              value={condition.value_to}
              onChange={(e) => onChange({ value_to: e.target.value })}
            />
          </>
        ) : (
          <Input
            aria-label={
              condition.operator === "regex"
                ? fm(builder.patternLabel, { number })
                : fm(builder.valueLabel, { number })
            }
            inputMode={isAmount ? "decimal" : undefined}
            numeric={isAmount}
            className={isAmount ? "w-28" : "min-w-48 flex-1"}
            value={condition.value}
            spellCheck={condition.operator === "regex" ? false : undefined}
            onChange={(e) => onChange({ value: e.target.value })}
          />
        )}
        {onRemove ? (
          <Button variant="ghost" size="sm" onClick={onRemove}>
            {fm(builder.removeCondition, { number })}
          </Button>
        ) : null}
      </div>
      {isAmount ? <p className="text-xs text-fg-muted">{fm(builder.amountHint)}</p> : null}
      {condition.operator === "regex" ? (
        <RegexTester pattern={condition.value} number={number} />
      ) : null}
    </li>
  );
}

export function RegexTester({ pattern, number }: { pattern: string; number: number }) {
  const fm = useFormatMessage();
  const [sample, setSample] = useState("");
  const result = highlightMatches(pattern, sample);
  return (
    <div className="flex flex-col gap-2 rounded-md bg-surface-subtle p-3" data-regex-tester="">
      <label className="flex flex-col gap-1 text-sm font-semibold text-fg">
        {fm(builder.sampleLabel, { number })}
        <textarea
          className={`${INPUT_BASE} min-h-16`}
          value={sample}
          placeholder={fm(builder.samplePlaceholder)}
          onChange={(e) => setSample(e.target.value)}
        />
      </label>
      {result.error ? (
        <p role="alert" className="text-sm font-semibold text-fg-danger">
          {fm(builder.patternInvalid)}
        </p>
      ) : sample ? (
        <>
          <p className="text-sm text-fg" aria-live="polite">
            {fm(builder.matchCount, { count: result.count })}
          </p>
          <p
            className="whitespace-pre-wrap break-words rounded border border-border bg-surface p-2 font-mono text-sm text-fg"
            data-highlighted=""
          >
            {result.parts.map((part, i) =>
              part.match ? (
                <mark key={i} className="rounded-sm bg-surface-warning-subtle text-fg">
                  {part.text}
                </mark>
              ) : (
                <span key={i}>{part.text}</span>
              ),
            )}
          </p>
        </>
      ) : null}
      <p className="text-xs text-fg-muted">{fm(builder.regexHint)}</p>
    </div>
  );
}
