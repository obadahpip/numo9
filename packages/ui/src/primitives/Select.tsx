"use client";

import * as RadixSelect from "@radix-ui/react-select";
import { forwardRef } from "react";

import { ChevronDownIcon } from "../shell/icons";
import { cn } from "./cn";
import { INPUT_BASE } from "./Input";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectGroup {
  label: string;
  options: SelectOption[];
}

export interface SelectProps {
  /** Options, flat or grouped. */
  options: (SelectOption | SelectGroup)[];
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  invalid?: boolean;
  required?: boolean;
  name?: string;
  id?: string;
  /** Accessible name when no `<label for>` names the trigger. */
  "aria-label"?: string;
  "aria-labelledby"?: string;
  "aria-describedby"?: string;
  className?: string;
}

const isGroup = (entry: SelectOption | SelectGroup): entry is SelectGroup => "options" in entry;

/**
 * Select (A-10-T06, Radix): a short list chosen with the keyboard (↑↓, type-ahead, Enter) or
 * pointer. For long or searchable lists use `Combobox`.
 */
export const Select = forwardRef<HTMLButtonElement, SelectProps>(function Select(
  { options, placeholder, invalid = false, className, id, ...props },
  ref,
) {
  const {
    "aria-label": ariaLabel,
    "aria-labelledby": labelledBy,
    "aria-describedby": describedBy,
    ...root
  } = props;
  return (
    <RadixSelect.Root {...root}>
      <RadixSelect.Trigger
        ref={ref}
        id={id}
        aria-label={ariaLabel}
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        aria-invalid={invalid || undefined}
        className={cn(
          INPUT_BASE,
          "inline-flex items-center justify-between gap-2 text-start data-[placeholder]:text-fg-subtle",
          invalid ? "border-border-danger" : "border-border-strong",
          className,
        )}
      >
        <RadixSelect.Value placeholder={placeholder} />
        <RadixSelect.Icon className="text-fg-muted">
          <ChevronDownIcon />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>
      <RadixSelect.Portal>
        <RadixSelect.Content
          position="popper"
          sideOffset={4}
          className="z-50 max-h-80 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md border border-border bg-surface text-fg shadow-elevation-3"
        >
          <RadixSelect.Viewport className="p-1">
            {options.map((entry) =>
              isGroup(entry) ? (
                <RadixSelect.Group key={entry.label}>
                  <RadixSelect.Label className="px-3 pt-2 pb-1 text-xs font-bold text-fg-muted">
                    {entry.label}
                  </RadixSelect.Label>
                  {entry.options.map((option) => (
                    <Item key={option.value} option={option} />
                  ))}
                </RadixSelect.Group>
              ) : (
                <Item key={entry.value} option={entry} />
              ),
            )}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
});

function Item({ option }: { option: SelectOption }) {
  return (
    <RadixSelect.Item
      value={option.value}
      disabled={option.disabled}
      className="relative flex min-h-touch-target cursor-pointer items-center rounded-sm ps-8 pe-3 text-sm outline-none select-none data-[disabled]:text-fg-disabled data-[highlighted]:bg-surface-muted"
    >
      <RadixSelect.ItemIndicator className="absolute start-2 inline-flex items-center">
        <CheckIcon />
      </RadixSelect.ItemIndicator>
      <RadixSelect.ItemText>{option.label}</RadixSelect.ItemText>
    </RadixSelect.Item>
  );
}

export function CheckIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M5 12l5 5 9-10" />
    </svg>
  );
}
