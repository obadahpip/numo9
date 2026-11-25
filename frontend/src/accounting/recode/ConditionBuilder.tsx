"use client";

/**
 * Find & recode — the condition builder (C-07-T10): All / Any, then rows of field · operator ·
 * value, each value input typed for its field (a date picker for dates, a numeric box for
 * amounts, the chart's accounts for account fields, fixed choices for type / status / book, a
 * category + option pair for tracking, nothing for "is empty"; a range takes two). The rows are
 * serialised to the API's search with `serialise()` (`conditions.ts`).
 */
import { Button, CloseIcon, IconButton, INPUT_BASE, PlusIcon } from "@numo9/ui";
import { useId } from "react";

import { useFormatMessage } from "@/i18n";

import type { Match } from "./api";
import { FIELD_KEYS, FIELDS, newRow, withField, type FieldKey, type Row } from "./conditions";
import { rm } from "./messages";

export interface AccountOption {
  id: string;
  label: string;
}

export interface ConditionBuilderProps {
  match: Match;
  rows: Row[];
  accounts: AccountOption[];
  onMatchChange: (match: Match) => void;
  onRowsChange: (rows: Row[]) => void;
  /** Row ids without a value (shown invalid after a search attempt). */
  invalid?: string[];
}

const control = `${INPUT_BASE} border-border`;

export function ConditionBuilder({
  match,
  rows,
  accounts,
  onMatchChange,
  onRowsChange,
  invalid = [],
}: ConditionBuilderProps) {
  const fm = useFormatMessage();
  const ids = useId();
  const update = (id: string, patch: Partial<Row>) =>
    onRowsChange(rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));

  return (
    <fieldset className="flex flex-col gap-3" data-condition-builder="">
      <legend className="text-base font-semibold text-fg">{fm(rm.conditions)}</legend>
      <label className="flex flex-col gap-1 text-sm text-fg">
        {fm(rm.match)}
        <select
          className={control}
          value={match}
          onChange={(event) => onMatchChange(event.target.value as Match)}
          data-match=""
        >
          {(["all", "any"] as const).map((value) => (
            <option key={value} value={value}>
              {fm(rm.matchOption, { match: value })}
            </option>
          ))}
        </select>
      </label>
      <ol className="flex flex-col gap-3">
        {rows.map((row, index) => {
          const spec = FIELDS[row.field];
          const kind = spec.input(row.op);
          const range = row.op === "between";
          const bad = invalid.includes(row.id);
          const prefix = `${ids}-${row.id}`;
          return (
            <li
              key={row.id}
              aria-label={fm(rm.conditionRow, { position: index + 1 })}
              className="flex flex-col gap-2 rounded-md border border-border p-2"
              data-condition={row.field}
            >
              <div className="flex items-end gap-2">
                <label className="flex flex-1 flex-col gap-1 text-xs text-fg-muted">
                  {fm(rm.field)}
                  <select
                    className={control}
                    value={row.field}
                    onChange={(event) =>
                      onRowsChange(
                        rows.map((r) =>
                          r.id === row.id ? withField(r, event.target.value as FieldKey) : r,
                        ),
                      )
                    }
                    data-field=""
                  >
                    {FIELD_KEYS.map((key) => (
                      <option key={key} value={key}>
                        {fm(rm.fieldName, { field: key })}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-1 flex-col gap-1 text-xs text-fg-muted">
                  {fm(rm.op)}
                  <select
                    className={control}
                    value={row.op}
                    onChange={(event) => update(row.id, { op: event.target.value, value2: "" })}
                    data-op=""
                  >
                    {spec.ops.map((op) => (
                      <option key={op} value={op}>
                        {fm(rm.opName, { op })}
                      </option>
                    ))}
                  </select>
                </label>
                <IconButton
                  label={fm(rm.removeCondition, { position: index + 1 })}
                  icon={<CloseIcon />}
                  size="sm"
                  onClick={() => onRowsChange(rows.filter((r) => r.id !== row.id))}
                />
              </div>
              {kind === "none" ? null : (
                <div className="flex flex-wrap items-end gap-2">
                  {kind === "tracking" ? (
                    <>
                      <ValueInput
                        id={`${prefix}-v`}
                        label={fm(rm.category)}
                        value={row.value}
                        invalid={bad && !row.value.trim()}
                        onChange={(value) => update(row.id, { value })}
                      />
                      <ValueInput
                        id={`${prefix}-v2`}
                        label={fm(rm.option)}
                        value={row.value2}
                        invalid={bad && !row.value2.trim()}
                        onChange={(value2) => update(row.id, { value2 })}
                      />
                    </>
                  ) : kind === "choice" ? (
                    <label className="flex flex-1 flex-col gap-1 text-xs text-fg-muted">
                      {fm(rm.value)}
                      <select
                        className={control}
                        value={row.value}
                        onChange={(event) => update(row.id, { value: event.target.value })}
                        data-value=""
                      >
                        {(spec.choices ?? []).map((value) => (
                          <option key={value} value={value}>
                            {fm(rm.choice, { value })}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : kind === "account" ? (
                    <label className="flex flex-1 flex-col gap-1 text-xs text-fg-muted">
                      {fm(rm.value)}
                      <select
                        className={control}
                        value={row.value}
                        aria-invalid={bad && !row.value ? true : undefined}
                        onChange={(event) => update(row.id, { value: event.target.value })}
                        data-value=""
                      >
                        <option value="">{fm(rm.chooseAccount)}</option>
                        {accounts.map((account) => (
                          <option key={account.id} value={account.id}>
                            {account.label}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : (
                    <>
                      <ValueInput
                        id={`${prefix}-v`}
                        label={fm(rm.value)}
                        type={kind === "date" ? "date" : "text"}
                        numeric={kind === "amount"}
                        hint={row.op === "in" ? fm(rm.inHint) : undefined}
                        value={row.value}
                        invalid={bad && !row.value.trim()}
                        onChange={(value) => update(row.id, { value })}
                      />
                      {range ? (
                        <ValueInput
                          id={`${prefix}-v2`}
                          label={fm(rm.valueTo)}
                          type={kind === "date" ? "date" : "text"}
                          numeric={kind === "amount"}
                          value={row.value2}
                          invalid={bad && !row.value2.trim()}
                          onChange={(value2) => update(row.id, { value2 })}
                        />
                      ) : null}
                    </>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ol>
      <div>
        <Button variant="secondary" onClick={() => onRowsChange([...rows, newRow()])}>
          <PlusIcon />
          {fm(rm.addCondition)}
        </Button>
      </div>
      {invalid.length ? (
        <p role="alert" className="text-sm text-fg-danger">
          {fm(rm.incomplete)}
        </p>
      ) : null}
    </fieldset>
  );
}

function ValueInput({
  id,
  label,
  value,
  onChange,
  invalid,
  type = "text",
  numeric = false,
  hint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  invalid?: boolean;
  type?: "text" | "date";
  numeric?: boolean;
  hint?: string;
}) {
  return (
    <div className="flex flex-1 flex-col gap-1 text-xs text-fg-muted">
      <label htmlFor={id} className="flex flex-col gap-1">
        {label}
        <input
          id={id}
          type={type}
          inputMode={numeric ? "decimal" : undefined}
          className={`${control} ${numeric ? "text-end tabular-nums" : ""}`}
          value={value}
          aria-invalid={invalid ? true : undefined}
          aria-describedby={hint ? `${id}-hint` : undefined}
          onChange={(event) => onChange(event.target.value)}
        />
      </label>
      {hint ? (
        <span id={`${id}-hint`} className="text-fg-subtle">
          {hint}
        </span>
      ) : null}
    </div>
  );
}
