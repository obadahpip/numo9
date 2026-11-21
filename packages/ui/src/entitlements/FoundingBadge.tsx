import { Badge } from "../primitives/Badge";
import { cn } from "../primitives/cn";

/** The four-digit founding number: 427 → "0427" (U-08-T09). */
export function formatFoundingNumber(slot: number): string {
  return String(Math.trunc(slot)).padStart(4, "0");
}

export interface FoundingBadgeProps {
  /** The organisation's founding slot number (1…1,000). */
  slot: number;
  /**
   * The visible text, translated by the app — e.g. `Founding organisation #0427`
   * (use `formatFoundingNumber` for the number).
   */
  label: string;
  /** Hover/assistive explanation, e.g. "One of the first 1,000 organisations: every product included". */
  description?: string;
  className?: string;
}

/**
 * Founding badge (U-08-T09): marks one of the first 1,000 organisations on the organisation
 * profile (and later the client portal). Accent tone with a star; the text always carries the
 * number, so colour is never the only cue.
 */
export function FoundingBadge({ slot, label, description, className }: FoundingBadgeProps) {
  return (
    <Badge
      tone="accent"
      className={cn("gap-1", className)}
      title={description}
      data-founding-slot={slot}
    >
      <span className="inline-flex items-center gap-1">
        <svg
          aria-hidden="true"
          viewBox="0 0 16 16"
          className="size-3 shrink-0 fill-current"
          focusable="false"
        >
          <path d="M8 1.2l1.95 4.2 4.6.5-3.42 3.1.95 4.55L8 11.2l-4.08 2.35.95-4.55L1.45 5.9l4.6-.5z" />
        </svg>
        {label}
      </span>
    </Badge>
  );
}
