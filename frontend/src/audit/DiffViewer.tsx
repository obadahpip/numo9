"use client";

import { cn } from "@numo9/ui";

import { useFormatMessage } from "@/i18n";

import type { AuditChange, AuditValue } from "./api";
import { m } from "./messages";

/** A value as people read it (markers for masked, cut and related values). */
export function useValueText() {
  const fm = useFormatMessage();
  return (value: AuditValue): string => {
    if (value === null || value === undefined || value === "") return fm(m.empty_value);
    if (typeof value === "boolean") return fm(value ? m.yes : m.no);
    if (typeof value === "string" || typeof value === "number") return String(value);
    if (Array.isArray(value)) return value.map((v) => String(v)).join(", ");
    if ("masked" in value && value.masked) return fm(m.hidden);
    if ("truncated" in value && value.truncated) {
      return fm(m.truncated, { text: String(value.text), length: Number(value.length) });
    }
    if ("label" in value && typeof value.label === "string") {
      return value.label || String((value as { id?: unknown }).id ?? "");
    }
    return JSON.stringify(value);
  };
}

/**
 * DiffViewer (A-04-T09): each changed field with its value before and after. Before/after are
 * named in text (screen readers read "Amount, Before 100.00, After 120.50") and marked with − / +
 * signs as well as colour — never colour alone. Masked fields say they changed, never the value.
 */
export function DiffViewer({
  changes,
  className,
}: Readonly<{ changes: AuditChange[]; className?: string }>) {
  const fm = useFormatMessage();
  const text = useValueText();
  if (changes.length === 0) {
    return <p className={cn("text-fg-muted", className)}>{fm(m.noChanges)}</p>;
  }
  return (
    <dl aria-label={fm(m.diff)} className={cn("flex flex-col gap-3", className)} data-diff="">
      {changes.map((change) => (
        <div
          key={change.field}
          className="rounded-md border border-border p-3"
          data-diff-field={change.field}
        >
          <dt className="font-semibold">{change.label}</dt>
          {change.masked ? (
            <dd className="text-fg-muted">{fm(m.hiddenNote)}</dd>
          ) : (
            <>
              <dd className="mt-1 flex gap-2 rounded bg-surface-danger-subtle px-2 py-1">
                <MinusIcon />
                <span className="font-medium">{fm(m.before)}</span>
                <span className="break-all whitespace-pre-wrap" data-diff-old="">
                  {text(change.old)}
                </span>
              </dd>
              <dd className="mt-1 flex gap-2 rounded bg-surface-success-subtle px-2 py-1">
                <PlusIcon />
                <span className="font-medium">{fm(m.after)}</span>
                <span className="break-all whitespace-pre-wrap" data-diff-new="">
                  {text(change.new)}
                </span>
              </dd>
            </>
          )}
        </div>
      ))}
    </dl>
  );
}

function MinusIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" className="mt-1 size-3 shrink-0 text-fg-danger">
      <path d="M3 8h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 16 16" className="mt-1 size-3 shrink-0 text-fg-success">
      <path d="M3 8h10M8 3v10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
