"use client";

import * as RadixRadio from "@radix-ui/react-radio-group";
import { forwardRef, useId, type ComponentPropsWithoutRef, type ReactNode } from "react";

import { cn } from "./cn";

export interface RadioOption {
  value: string;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}

export interface RadioGroupProps extends Omit<
  ComponentPropsWithoutRef<typeof RadixRadio.Root>,
  "children"
> {
  options: RadioOption[];
  invalid?: boolean;
}

/**
 * Radio group (A-10-T06, Radix): one choice from a few visible options; arrow keys move and
 * select. Name the group with `aria-label` / `aria-labelledby` (a `Fieldset` legend in forms).
 */
export const RadioGroup = forwardRef<HTMLDivElement, RadioGroupProps>(function RadioGroup(
  { options, invalid = false, className, ...props },
  ref,
) {
  const baseId = useId();
  return (
    <RadixRadio.Root
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn("flex flex-col", className)}
      {...props}
    >
      {options.map((option, index) => {
        const id = `${baseId}-${index}`;
        return (
          <div key={option.value} className="flex min-h-touch-target items-start gap-3 py-2.5">
            <RadixRadio.Item
              id={id}
              value={option.value}
              disabled={option.disabled}
              aria-describedby={option.description ? `${id}-description` : undefined}
              className={cn(
                "inline-flex size-5 shrink-0 items-center justify-center rounded-full border-2 bg-surface",
                "data-[state=checked]:border-surface-inverse disabled:cursor-not-allowed disabled:opacity-50",
                invalid ? "border-border-danger" : "border-border-strong",
              )}
            >
              <RadixRadio.Indicator className="block size-2.5 rounded-full bg-surface-inverse" />
            </RadixRadio.Item>
            <div className="text-sm">
              <label htmlFor={id} className="cursor-pointer text-fg">
                {option.label}
              </label>
              {option.description ? (
                <p id={`${id}-description`} className="text-xs text-fg-muted">
                  {option.description}
                </p>
              ) : null}
            </div>
          </div>
        );
      })}
    </RadixRadio.Root>
  );
});
