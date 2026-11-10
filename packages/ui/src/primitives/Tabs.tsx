"use client";

import * as RadixTabs from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

import { cn } from "./cn";

export interface TabItem {
  value: string;
  label: ReactNode;
  /** Optional count shown after the label, e.g. contacts per role. */
  count?: number;
  content: ReactNode;
  disabled?: boolean;
}

export interface TabsProps {
  items: TabItem[];
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  /** Accessible name of the tab list. */
  label: string;
  className?: string;
}

/**
 * Tabs (A-10-T06, Radix): ←/→ move between tabs, Home/End jump; each panel is labelled by its
 * tab. Use for views of one record or list (contact roles), not for navigation between modules.
 */
export function Tabs({ items, value, defaultValue, onValueChange, label, className }: TabsProps) {
  return (
    <RadixTabs.Root
      value={value}
      defaultValue={defaultValue ?? items[0]?.value}
      onValueChange={onValueChange}
      className={className}
    >
      <RadixTabs.List
        aria-label={label}
        className="flex gap-1 overflow-x-auto border-b border-border"
      >
        {items.map((item) => (
          <RadixTabs.Trigger
            key={item.value}
            value={item.value}
            disabled={item.disabled}
            className={cn(
              "relative inline-flex min-h-touch-target items-center gap-2 px-4 text-sm font-medium whitespace-nowrap text-fg-muted",
              "hover:text-fg data-[state=active]:font-semibold data-[state=active]:text-fg",
              "data-[state=active]:after:absolute data-[state=active]:after:inset-x-2 data-[state=active]:after:bottom-0 data-[state=active]:after:h-1 data-[state=active]:after:bg-surface-accent",
              "disabled:cursor-not-allowed disabled:opacity-50",
            )}
          >
            {item.label}
            {item.count !== undefined ? (
              <span className="rounded-full bg-surface-muted px-2 text-xs tabular-nums text-fg">
                {item.count}
              </span>
            ) : null}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {items.map((item) => (
        <RadixTabs.Content key={item.value} value={item.value} className="pt-4 outline-none">
          {item.content}
        </RadixTabs.Content>
      ))}
    </RadixTabs.Root>
  );
}
