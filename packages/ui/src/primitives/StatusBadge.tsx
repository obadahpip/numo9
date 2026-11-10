import { Badge, type BadgeTone } from "./Badge";

/**
 * The one status vocabulary (A-10-T06, Phase 0 UX principle 14): every status of every document
 * type maps to one tone here, so a status looks the same on tiles, lists and detail pages.
 * Modules add their statuses to this map (not their own colours). Labels are i18n messages
 * passed by the app.
 */
export const STATUS_TONES = {
  // Documents (invoices, bills, quotes, purchase orders — Phase 1)
  draft: "neutral",
  awaiting_approval: "warning",
  approved: "info",
  sent: "info",
  partially_paid: "accent",
  paid: "success",
  overdue: "danger",
  voided: "neutral",
  // Journals (C-02)
  posted: "success",
  reversed: "neutral",
  unbalanced: "danger",
  // Organisation subscription (U-04/U-05)
  demo: "info",
  trial: "accent",
  active: "success",
  grace: "warning",
  read_only: "warning",
  cancelled: "neutral",
  // Files (A-06)
  scanning: "info",
  infected: "danger",
  ready: "success",
  // Generic
  archived: "neutral",
  failed: "danger",
} as const satisfies Record<string, BadgeTone>;

export type StatusKey = keyof typeof STATUS_TONES;

export interface StatusBadgeProps {
  status: StatusKey;
  /** Translated status name, e.g. "Awaiting approval". */
  label: string;
  className?: string;
}

/** Status badge: tone from the shared status map, text from the app (always shown). */
export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  return (
    <Badge tone={STATUS_TONES[status]} dot data-status={status} className={className}>
      {label}
    </Badge>
  );
}
