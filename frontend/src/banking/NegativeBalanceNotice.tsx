"use client";

/**
 * The app's negative-balance panel (F-07-T07): the design-system `NegativeBalancePanel` with the
 * translated texts, fed by what the API answered — the shortfalls of a refusal
 * (`ledger.journal.negative_cash` → block, `ledger.journal.override_reason_required` → warn) or
 * of a check. Used by the spend / receive and journal forms; the transfer dialog (F-06-T07) and
 * payment forms import it too. Remedies are given by the form (F-07-T06 adds suggestions).
 */
import { NegativeBalancePanel, type NegativeBalanceRemedy } from "@numo9/ui";

import { useFormatMessage } from "@/i18n";

import { cash } from "./cashControlMessages";

export const NEGATIVE_BLOCK = "ledger.journal.negative_cash";
export const NEGATIVE_WARN = "ledger.journal.override_reason_required";
export const MIN_OVERRIDE_REASON = 10;

export interface NoticeShortfall {
  account: { id: string };
  message: string;
  action?: string;
}

/** The panel's state for a refusal code, or null when it isn't a negative-balance refusal. */
export function negativeState(code: string | undefined): "warn" | "block" | null {
  if (code === NEGATIVE_BLOCK) return "block";
  if (code === NEGATIVE_WARN) return "warn";
  return null;
}

export interface NegativeBalanceNoticeProps {
  state: "warn" | "block";
  shortfalls: readonly NoticeShortfall[];
  /** The server's explanation, shown instead of the generic text when given. */
  detail?: string;
  remedies?: readonly NegativeBalanceRemedy[];
  /** Warn: the reason field (leave out when the form asks for it elsewhere). */
  reason?: string;
  onReasonChange?: (reason: string) => void;
}

export function NegativeBalanceNotice({
  state,
  shortfalls,
  detail,
  remedies,
  reason,
  onReasonChange,
}: NegativeBalanceNoticeProps) {
  const fm = useFormatMessage();
  return (
    <NegativeBalancePanel
      state={state}
      title={fm(cash.title)}
      shortfalls={shortfalls.map((s) => ({ id: s.account.id, message: s.message }))}
      body={detail ?? fm(state === "block" ? cash.blockBody : cash.warnBody)}
      overrider={fm(cash.overrider)}
      remedies={remedies}
      remediesLabel={fm(cash.remedies)}
      reason={reason}
      onReasonChange={onReasonChange}
      reasonLabel={fm(cash.reason)}
      reasonHint={fm(cash.reasonHint, { min: MIN_OVERRIDE_REASON })}
      minReason={MIN_OVERRIDE_REASON}
    />
  );
}
