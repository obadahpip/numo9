"use client";

import * as RadixSwitch from "@radix-ui/react-switch";
import { forwardRef, useId, type ComponentPropsWithoutRef, type ReactNode } from "react";

import { cn } from "./cn";

export interface SwitchProps extends Omit<
  ComponentPropsWithoutRef<typeof RadixSwitch.Root>,
  "children"
> {
  /** Visible label; omit only when `aria-label` names the switch. */
  label?: ReactNode;
  description?: ReactNode;
}

/**
 * Switch (A-10-T06, Radix): an on/off setting that applies immediately (e.g. "Compact density").
 * For a choice saved with a form, use `Checkbox`.
 */
export const Switch = forwardRef<HTMLButtonElement, SwitchProps>(function Switch(
  { label, description, className, id, ...props },
  ref,
) {
  const autoId = useId();
  const switchId = id ?? autoId;
  const control = (
    <RadixSwitch.Root
      ref={ref}
      id={switchId}
      aria-describedby={description ? `${switchId}-description` : props["aria-describedby"]}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border-2 border-transparent",
        "bg-neutral-500 data-[state=checked]:bg-surface-inverse disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <RadixSwitch.Thumb className="block size-5 rounded-full bg-surface shadow-elevation-1 transition-transform data-[state=checked]:translate-x-5 rtl:data-[state=checked]:-translate-x-5" />
    </RadixSwitch.Root>
  );
  if (!label) return control;
  return (
    <div className="flex min-h-touch-target items-center justify-between gap-4 py-2">
      <div className="text-sm">
        <label htmlFor={switchId} className="cursor-pointer text-fg">
          {label}
        </label>
        {description ? (
          <p id={`${switchId}-description`} className="text-xs text-fg-muted">
            {description}
          </p>
        ) : null}
      </div>
      {control}
    </div>
  );
});
