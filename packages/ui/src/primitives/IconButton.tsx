"use client";

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { cn } from "./cn";
import { Tooltip } from "./Tooltip";

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Accessible name — required: an icon alone names nothing. Also shown as the tooltip. */
  label: string;
  icon: ReactNode;
  variant?: "ghost" | "secondary" | "inverse";
  size?: "md" | "sm";
  /** Show `label` as a tooltip on hover/focus (default true). */
  tooltip?: boolean;
}

const VARIANTS = {
  ghost: "text-fg hover:bg-surface-muted",
  secondary: "text-fg border border-border-strong bg-surface hover:bg-surface-muted",
  inverse: "text-fg-inverse hover:bg-surface-inverse-hover",
} as const;

/** Icon-only button (A-10-T06): 44 px target, `aria-label` from `label`, optional tooltip. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, variant = "ghost", size = "md", tooltip = true, className, type, ...props },
  ref,
) {
  const button = (
    <button
      ref={ref}
      type={type ?? "button"}
      aria-label={label}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-md disabled:cursor-not-allowed disabled:opacity-50",
        size === "md" ? "size-touch-target" : "size-8",
        VARIANTS[variant],
        className,
      )}
      {...props}
    >
      {icon}
    </button>
  );
  return tooltip ? <Tooltip content={label}>{button}</Tooltip> : button;
});
