"use client";

import type { ReactNode } from "react";

import { Button } from "../primitives/Button";
import { cn } from "../primitives/cn";

export interface ErrorStateProps {
  /** What failed, naming the thing: "Organisations couldn't be loaded". */
  title: string;
  /** Why (if known) and what to do (microcopy §3.5 — no codes alone, no blame, never "Oops"). */
  body?: ReactNode;
  retryLabel: string;
  onRetry: () => void;
  /** "Report a problem": sends the reference to support (A-07/U-06); omitted → hidden. */
  reportLabel?: string;
  onReport?: () => void;
  /** Support reference (request id / Sentry event), shown so support can find it. */
  reference?: string;
  /** e.g. (ref) → "Reference: 7f3c2a10". */
  referenceLabel?: (reference: string) => string;
  retrying?: boolean;
  headingLevel?: 2 | 3;
  className?: string;
}

/** Error state (A-10-T12): a load failed — say what, offer Try again and a way to report it. */
export function ErrorState({
  title,
  body,
  retryLabel,
  onRetry,
  reportLabel,
  onReport,
  reference,
  referenceLabel,
  retrying = false,
  headingLevel = 2,
  className,
}: ErrorStateProps) {
  const Heading = `h${headingLevel}` as const;
  return (
    <div
      role="alert"
      data-state="error"
      className={cn("flex flex-col items-center gap-3 px-6 py-12 text-center", className)}
    >
      <span
        aria-hidden="true"
        className="inline-flex size-12 items-center justify-center rounded-full bg-surface-danger-subtle text-xl font-bold text-fg-danger"
      >
        !
      </span>
      <Heading className="text-lg font-semibold text-fg">{title}</Heading>
      {body ? <div className="max-w-md text-sm text-fg-muted">{body}</div> : null}
      <div className="mt-2 flex flex-wrap justify-center gap-2">
        <Button variant="primary" onClick={onRetry} loading={retrying}>
          {retryLabel}
        </Button>
        {reportLabel && onReport ? <Button onClick={onReport}>{reportLabel}</Button> : null}
      </div>
      {reference && referenceLabel ? (
        <p className="font-mono text-xs text-fg-muted select-all">{referenceLabel(reference)}</p>
      ) : null}
    </div>
  );
}
