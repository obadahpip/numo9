"use client";

/**
 * Journal type segmented control (C-03-T11): General · Adjusting · Reclass · Tax adjustment, each
 * with its description (shown under the control for the chosen type, and as each segment's
 * tooltip). The system types (Closing, Payroll, Depreciation) are posted by Numo9's own
 * processes and never offered. Native radio buttons: arrows move, the group is one tab stop.
 */
import { useId } from "react";

import { useFormatMessage } from "@/i18n";

import { SELECTABLE_TYPES, type JournalTypeKey } from "./api";
import { wm } from "./messages";

const LABELS = {
  general: wm.typeGeneral,
  adjusting: wm.typeAdjusting,
  reclass: wm.typeReclass,
  tax_adjustment: wm.typeTaxAdjustment,
} as const;

const HELP = {
  general: wm.helpGeneral,
  adjusting: wm.helpAdjusting,
  reclass: wm.helpReclass,
  tax_adjustment: wm.helpTaxAdjustment,
} as const;

export function JournalTypePicker({
  value,
  onChange,
}: {
  value: JournalTypeKey;
  onChange: (value: JournalTypeKey) => void;
}) {
  const fm = useFormatMessage();
  const name = useId();
  const helpId = useId();
  return (
    <fieldset className="flex flex-col gap-1">
      <legend className="mb-1 text-sm font-medium text-fg">{fm(wm.type)}</legend>
      <div
        className="inline-flex w-fit flex-wrap rounded-md border border-border"
        role="presentation"
      >
        {SELECTABLE_TYPES.map((key) => (
          <label
            key={key}
            title={fm(HELP[key])}
            className="flex min-h-touch-target cursor-pointer items-center px-3 text-sm text-fg has-[:checked]:bg-surface-accent has-[:checked]:font-semibold has-[:checked]:text-fg-on-accent has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus"
          >
            <input
              type="radio"
              name={name}
              value={key}
              checked={value === key}
              onChange={() => onChange(key)}
              aria-describedby={value === key ? helpId : undefined}
              className="sr-only"
            />
            {fm(LABELS[key])}
          </label>
        ))}
      </div>
      <p id={helpId} className="text-xs text-fg-muted">
        {fm(HELP[value])}
      </p>
    </fieldset>
  );
}
