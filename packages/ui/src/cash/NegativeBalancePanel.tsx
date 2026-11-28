"use client";

import { useId, type ReactNode } from "react";

import { Button } from "../primitives/Button";
import { cn } from "../primitives/cn";

/**
 * Negative-balance panel (F-07-T07): shown **inline in the form** (not a modal) when saving would
 * take a bank or cash account below zero — "Petty Cash will be −994.17 on 15 Jun 2026".
 *
 * - `warn` — the organisation's policy lets the person post anyway with a reason: the panel holds
 *   the reason field (`reason` / `onReasonChange`, at least `minReason` characters);
 * - `block` — the policy refuses it for this person: the panel names who can override
 *   (`overrider`) and offers the remedies only.
 *
 * Remedies (up to two buttons, e.g. "Fund petty cash from Chequing", "Record as owner paid") come
 * from the caller (F-07-T06's suggestion service); every text is a prop (the app translates).
 * Used by the spend / receive, journal, transfer and payment forms.
 */
export type NegativeBalanceState = "warn" | "block";

export interface NegativeBalanceShortfall {
  /** Stable key (the account id). */
  id: string;
  /** "Petty Cash would be −994.17 on 15 Jun 2026". */
  message: string;
}

export interface NegativeBalanceRemedy {
  id: string;
  label: string;
  onSelect: () => void;
  disabled?: boolean;
}

export interface NegativeBalancePanelProps {
  state: NegativeBalanceState;
  /** "This would take a bank or cash account below zero". */
  title: string;
  shortfalls: readonly NegativeBalanceShortfall[];
  /** Why / what to do (the server's explanation). */
  body?: ReactNode;
  /** Block: who can override ("An adviser, or someone allowed to approve negative balances"). */
  overrider?: ReactNode;
  /** At most two are shown. */
  remedies?: readonly NegativeBalanceRemedy[];
  remediesLabel?: string;
  /** Warn: the reason, controlled by the form. Leave out to collect it elsewhere. */
  reason?: string;
  onReasonChange?: (reason: string) => void;
  reasonLabel?: string;
  /** "At least 10 characters — kept with the journal." */
  reasonHint?: string;
  minReason?: number;
  className?: string;
}

export const MAX_REMEDIES = 2;

function WarningIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      <path d="M12 9v4M12 17h.01" />
    </svg>
  );
}

export function NegativeBalancePanel({
  state,
  title,
  shortfalls,
  body,
  overrider,
  remedies = [],
  remediesLabel,
  reason,
  onReasonChange,
  reasonLabel,
  reasonHint,
  minReason = 10,
  className,
}: NegativeBalancePanelProps) {
  const ids = useId();
  const titleId = `${ids}-title`;
  const hintId = `${ids}-hint`;
  const reasonId = `${ids}-reason`;
  const shown = remedies.slice(0, MAX_REMEDIES);
  const wantsReason = state === "warn" && onReasonChange !== undefined;
  const short = wantsReason && (reason ?? "").trim().length < minReason;
  return (
    <section
      role={state === "block" ? "alert" : "status"}
      aria-labelledby={titleId}
      data-negative-balance={state}
      className={cn(
        "flex gap-3 rounded-md border p-3 text-sm",
        state === "block"
          ? "border-border-danger bg-surface-danger-subtle"
          : "border-border-strong bg-surface-warning-subtle",
        className,
      )}
    >
      <span className={state === "block" ? "text-fg-danger" : "text-fg-warning"}>
        <WarningIcon />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <h2 id={titleId} className="font-semibold text-fg">
          {title}
        </h2>
        <ul className="list-disc ps-5 font-medium text-fg" data-shortfalls="">
          {shortfalls.map((shortfall) => (
            <li key={shortfall.id}>{shortfall.message}</li>
          ))}
        </ul>
        {body ? <div className="text-fg">{body}</div> : null}
        {state === "block" && overrider ? (
          <p className="text-fg" data-overrider="">
            {overrider}
          </p>
        ) : null}
        {shown.length ? (
          <div
            className="flex flex-wrap gap-2"
            role="group"
            aria-label={remediesLabel ?? title}
            data-remedies=""
          >
            {shown.map((remedy) => (
              <Button
                key={remedy.id}
                type="button"
                size="sm"
                variant="secondary"
                disabled={remedy.disabled}
                onClick={remedy.onSelect}
                data-remedy={remedy.id}
              >
                {remedy.label}
              </Button>
            ))}
          </div>
        ) : null}
        {wantsReason ? (
          <div className="flex flex-col gap-1">
            <label htmlFor={reasonId} className="font-medium text-fg">
              {reasonLabel}
            </label>
            <textarea
              id={reasonId}
              value={reason ?? ""}
              onChange={(event) => onReasonChange(event.target.value)}
              rows={3}
              minLength={minReason}
              required
              aria-invalid={short && (reason ?? "").length > 0 ? true : undefined}
              aria-describedby={reasonHint ? hintId : undefined}
              className="rounded-md border border-border bg-surface p-2 text-sm text-fg"
              data-reason=""
            />
            {reasonHint ? (
              <span id={hintId} className="text-xs text-fg-muted">
                {reasonHint}
              </span>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}

/** Whether the reason in the panel is long enough to post past a warning. */
export function reasonIsEnough(reason: string, minReason = 10): boolean {
  return reason.trim().length >= minReason;
}
