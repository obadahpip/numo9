import type { ReactNode } from "react";

import { cn } from "../primitives/cn";
import { Illustration, type IllustrationName } from "./illustrations";

export interface EmptyStateProps {
  title: string;
  /** What the list will hold and how to start; one or two sentences. */
  body?: ReactNode;
  /** Built-in illustration name or your own decorative node. */
  illustration?: IllustrationName | ReactNode;
  /** 1–3 actions (Buttons or links), the primary first. More than 3 are not shown. */
  actions?: ReactNode[];
  headingLevel?: 2 | 3;
  /** Less padding, for small panels. */
  compact?: boolean;
  className?: string;
}

export const MAX_EMPTY_STATE_ACTIONS = 3;

/**
 * Empty state (A-10-T12): the one "nothing here yet" design for every list — illustration, what
 * belongs here, and 1–3 ways to start (e.g. "New contact", "Import contacts").
 */
export function EmptyState({
  title,
  body,
  illustration,
  actions = [],
  headingLevel = 2,
  compact = false,
  className,
}: EmptyStateProps) {
  const Heading = `h${headingLevel}` as const;
  if (actions.length > MAX_EMPTY_STATE_ACTIONS && process.env.NODE_ENV !== "production") {
    console.warn(
      `EmptyState "${title}": at most ${MAX_EMPTY_STATE_ACTIONS} actions; the rest are hidden.`,
    );
  }
  return (
    <div
      data-state="empty"
      className={cn(
        "flex flex-col items-center text-center",
        compact ? "gap-2 p-6" : "gap-3 px-6 py-12",
        className,
      )}
    >
      {illustration ? (
        <div className="mb-1">
          {typeof illustration === "string" ? (
            <Illustration name={illustration as IllustrationName} />
          ) : (
            illustration
          )}
        </div>
      ) : null}
      <Heading className="text-lg font-semibold text-fg">{title}</Heading>
      {body ? <div className="max-w-md text-sm text-fg-muted">{body}</div> : null}
      {actions.length ? (
        <div className="mt-2 flex flex-wrap justify-center gap-2">
          {actions.slice(0, MAX_EMPTY_STATE_ACTIONS)}
        </div>
      ) : null}
    </div>
  );
}
