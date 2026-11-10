"use client";

import { forwardRef, type InputHTMLAttributes, type ReactNode } from "react";

import { cn } from "./cn";

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "prefix"> {
  /** Error state: red border and `aria-invalid` (the message itself is rendered by the field). */
  invalid?: boolean;
  /** Fixed text or icon before / after the value, e.g. "$" or "CAD". Decorative. */
  prefix?: ReactNode;
  suffix?: ReactNode;
  /** Right-align figures (amounts, quantities). */
  numeric?: boolean;
}

export const INPUT_BASE =
  "min-h-touch-target w-full rounded-md border bg-surface px-3 text-sm text-fg " +
  "placeholder:text-fg-subtle disabled:cursor-not-allowed disabled:bg-surface-muted " +
  "disabled:text-fg-disabled read-only:bg-surface-subtle";

/** Text input (A-10-T06). Label and error message come from `Field` (A-10-T07) or `aria-label`. */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { invalid = false, prefix, suffix, numeric = false, className, ...props },
  ref,
) {
  const input = (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      data-numeric={numeric || undefined}
      className={cn(
        INPUT_BASE,
        invalid ? "border-border-danger" : "border-border-strong",
        numeric && "text-end tabular-nums",
        prefix ? "ps-8" : null,
        suffix ? "pe-12" : null,
        className,
      )}
      {...props}
    />
  );
  if (!prefix && !suffix) return input;
  return (
    <span className="relative block">
      {prefix ? (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 start-3 flex items-center text-sm text-fg-muted"
        >
          {prefix}
        </span>
      ) : null}
      {input}
      {suffix ? (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute inset-y-0 end-3 flex items-center text-xs text-fg-muted"
        >
          {suffix}
        </span>
      ) : null}
    </span>
  );
});
