"use client";

import { Slot } from "@radix-ui/react-slot";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

import { cn } from "./cn";
import { Spinner } from "./Spinner";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "link";
export type ButtonSize = "md" | "sm";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Busy: shows a spinner, sets `aria-busy` and blocks clicks (the label stays for screen readers). */
  loading?: boolean;
  /** Render the child element (e.g. a link) with button styling. */
  asChild?: boolean;
  /** Icon before the label. */
  icon?: ReactNode;
}

const VARIANTS: Record<ButtonVariant, string> = {
  // Black on yellow: the brand pair, 15.8:1 (A-10-T04).
  primary:
    "bg-surface-accent text-fg-on-accent hover:bg-surface-accent-hover border border-transparent",
  secondary: "bg-surface text-fg border border-border-strong hover:bg-surface-muted",
  ghost: "bg-transparent text-fg border border-transparent hover:bg-surface-muted",
  danger: "bg-surface text-fg-danger border border-border-danger hover:bg-surface-danger-subtle",
  link: "bg-transparent text-fg-link underline border border-transparent px-0",
};

const SIZES: Record<ButtonSize, string> = {
  // 44 px touch target on the default size (WCAG 2.5.5, Phase 0 UX principle 11).
  md: "min-h-touch-target px-4 text-sm",
  sm: "min-h-8 px-3 text-xs",
};

export const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-md font-semibold whitespace-nowrap " +
  "transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 " +
  "aria-disabled:cursor-not-allowed aria-disabled:opacity-50";

/**
 * Button (A-10-T06). Labels are verbs ("Save settings", not "OK") — microcopy rule §3.5 (6).
 * `type` defaults to "button" so a button inside a form never submits by accident.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "secondary",
    size = "md",
    loading = false,
    asChild = false,
    icon,
    className,
    children,
    disabled,
    type,
    onClick,
    ...props
  },
  ref,
) {
  const classes = cn(BUTTON_BASE, VARIANTS[variant], SIZES[size], className);
  if (asChild) {
    return (
      <Slot ref={ref} className={classes} {...props}>
        {children}
      </Slot>
    );
  }
  return (
    <button
      ref={ref}
      type={type ?? "button"}
      className={classes}
      disabled={disabled}
      aria-busy={loading || undefined}
      aria-disabled={loading || undefined}
      onClick={(event) => {
        if (loading) {
          event.preventDefault();
          return;
        }
        onClick?.(event);
      }}
      {...props}
    >
      {loading ? <Spinner /> : icon}
      {children}
    </button>
  );
});
