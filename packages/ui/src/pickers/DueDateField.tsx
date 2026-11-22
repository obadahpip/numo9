"use client";

import { useId } from "react";

import type { IsoDate } from "../format/dates";
import type { AppLocale } from "../format/locale";
import { cn } from "../primitives/cn";
import { DatePicker, type DatePickerLabels } from "./DatePicker";
import { daysBetween, dueDate, type PaymentTermOption } from "./dueDates";

export interface DueDateFieldLabels {
  label: string;
  /** Group name of the term chips: "Payment terms". */
  terms: string;
  /** (days) → "Due in 30 days"; 0 → "Due on the document date"; negative → "Overdue by 3 days". */
  dueIn: (days: number) => string;
  /** Shown when saving without a due date: "Enter a due date." */
  required: string;
  /** Under a due date before the document date: "The due date is before the invoice date." */
  beforeDate: string;
  date: DatePickerLabels;
}

export interface DueDateFieldProps {
  value: IsoDate | null;
  onChange: (value: IsoDate | null, term: PaymentTermOption | null) => void;
  /** The document date: chips and the "due in" helper count from it. */
  documentDate: IsoDate;
  /** The organisation's terms master (B-01-T05), in its order. */
  terms: readonly PaymentTermOption[];
  /** The term the due date came from (its chip shows as chosen). */
  termId?: string | null;
  today: IsoDate;
  locale: AppLocale;
  labels: DueDateFieldLabels;
  /** Set by the form after a save attempt without a due date (D-01-T17: required, gap-12). */
  showRequired?: boolean;
  disabled?: boolean;
  className?: string;
}

/**
 * Due date of a document (D-01-T17): required, defaulted from the terms; chips for the
 * organisation's payment terms set it from the document date (Net 30 → date + 30 days, EOM → the
 * month's last day…, the same rules as the server); "Due in N days" under it. Choosing a date by
 * hand clears the chosen term.
 */
export function DueDateField({
  value,
  onChange,
  documentDate,
  terms,
  termId = null,
  today,
  locale,
  labels,
  showRequired = false,
  disabled = false,
  className,
}: DueDateFieldProps) {
  const id = useId();
  const helpId = `${id}-help`;
  const errorId = `${id}-error`;
  const missing = showRequired && !value;
  const before = Boolean(value && value < documentDate);
  const days = value ? daysBetween(documentDate, value) : null;
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <label htmlFor={id} className="text-sm font-semibold text-fg">
        {labels.label}
        <span aria-hidden="true" className="text-fg-danger">
          {" "}
          *
        </span>
      </label>
      <DatePicker
        id={id}
        value={value}
        onChange={(next) => onChange(next, null)}
        locale={locale}
        today={today}
        base={documentDate}
        labels={labels.date}
        min={documentDate}
        required
        invalid={missing || before}
        disabled={disabled}
        aria-describedby={[missing || before ? errorId : "", value ? helpId : ""]
          .filter(Boolean)
          .join(" ")}
      />
      <div role="group" aria-label={labels.terms} className="flex flex-wrap gap-1">
        {terms.map((term) => {
          const chosen = term.id === termId;
          return (
            <button
              key={term.id}
              type="button"
              aria-pressed={chosen}
              disabled={disabled}
              onClick={() => onChange(dueDate(documentDate, term.terms_type, term.days), term)}
              className={cn(
                "inline-flex min-h-8 items-center rounded-full border px-3 text-xs font-semibold",
                chosen
                  ? "border-border-focus bg-surface-accent-subtle text-fg"
                  : "border-border text-fg-muted hover:bg-surface-muted",
              )}
            >
              {term.name}
            </button>
          );
        })}
      </div>
      {value && days !== null && !before ? (
        <p id={helpId} className="text-xs text-fg-muted" data-due-in={days}>
          {labels.dueIn(days)}
        </p>
      ) : null}
      {missing || before ? (
        <p id={errorId} role="alert" className="text-xs font-semibold text-fg-danger">
          {missing ? labels.required : labels.beforeDate}
        </p>
      ) : null}
    </div>
  );
}
