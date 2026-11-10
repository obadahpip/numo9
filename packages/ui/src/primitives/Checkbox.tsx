"use client";

import * as RadixCheckbox from "@radix-ui/react-checkbox";
import { forwardRef, useId, type ComponentPropsWithoutRef, type ReactNode } from "react";

import { cn } from "./cn";
import { CheckIcon } from "./Select";

export interface CheckboxProps extends Omit<
  ComponentPropsWithoutRef<typeof RadixCheckbox.Root>,
  "children"
> {
  /** Visible label; omit only when `aria-label` names the box (e.g. a grid row selector). */
  label?: ReactNode;
  description?: ReactNode;
  invalid?: boolean;
}

/** Checkbox (A-10-T06, Radix): checked, unchecked or indeterminate ("select all" of a grid). */
export const Checkbox = forwardRef<HTMLButtonElement, CheckboxProps>(function Checkbox(
  { label, description, invalid = false, className, id, ...props },
  ref,
) {
  const autoId = useId();
  const boxId = id ?? autoId;
  const box = (
    <RadixCheckbox.Root
      ref={ref}
      id={boxId}
      aria-invalid={invalid || undefined}
      aria-describedby={description ? `${boxId}-description` : props["aria-describedby"]}
      className={cn(
        "inline-flex size-5 shrink-0 items-center justify-center rounded-sm border-2 bg-surface",
        "data-[state=checked]:border-surface-inverse data-[state=checked]:bg-surface-inverse data-[state=checked]:text-fg-inverse",
        "data-[state=indeterminate]:border-surface-inverse data-[state=indeterminate]:bg-surface-inverse data-[state=indeterminate]:text-fg-inverse",
        "disabled:cursor-not-allowed disabled:opacity-50",
        invalid ? "border-border-danger" : "border-border-strong",
        className,
      )}
      {...props}
    >
      <RadixCheckbox.Indicator>
        {props.checked === "indeterminate" ? (
          <span className="block h-0.5 w-2.5 bg-current" />
        ) : (
          <CheckIcon />
        )}
      </RadixCheckbox.Indicator>
    </RadixCheckbox.Root>
  );
  if (!label) return box;
  return (
    <div className="flex min-h-touch-target items-start gap-3 py-2.5">
      {box}
      <div className="text-sm">
        <label htmlFor={boxId} className="cursor-pointer text-fg">
          {label}
        </label>
        {description ? (
          <p id={`${boxId}-description`} className="text-xs text-fg-muted">
            {description}
          </p>
        ) : null}
      </div>
    </div>
  );
});
