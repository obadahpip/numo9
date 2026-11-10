import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "./cn";

export type BadgeTone =
  "neutral" | "accent" | "info" | "success" | "warning" | "danger" | "inverse";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  /** Leading dot (status colour cue; the text always names the state). */
  dot?: boolean;
  children: ReactNode;
}

/** Text/background pairs from the contrast-checked tokens (A-10-T04), each ≥ 4.5:1. */
const TONES: Record<BadgeTone, string> = {
  neutral: "bg-surface-muted text-fg",
  accent: "bg-surface-accent-subtle text-fg-accent-strong",
  info: "bg-surface-info-subtle text-fg-info",
  success: "bg-surface-success-subtle text-fg-success",
  warning: "bg-surface-warning-subtle text-fg-warning",
  danger: "bg-surface-danger-subtle text-fg-danger",
  inverse: "bg-surface-inverse text-fg-inverse",
};

/** Badge (A-10-T06): a short label (type, tag, count). Colour is never the only cue. */
export function Badge({
  tone = "neutral",
  dot = false,
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 text-xs leading-5 font-semibold whitespace-nowrap",
        TONES[tone],
        className,
      )}
      {...props}
    >
      {dot ? (
        <span aria-hidden="true" className="size-1.5 shrink-0 rounded-full bg-current" />
      ) : null}
      <span className="truncate">{children}</span>
    </span>
  );
}
