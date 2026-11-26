/**
 * The difference meter's figures (C-05-T11), computed **in the browser** from the balances being
 * typed so the meter follows every keystroke (no round trip): debits, credits and their
 * difference, exactly (decimal strings, never floats). Amounts that don't parse yet count as
 * zero and are reported in `unreadable`.
 *
 * What the browser can't know — the receivable and payable controls against the open documents,
 * accounts that need a contact — comes from the server's difference (`reasons`), refreshed on
 * every save; `blockers()` merges both into why Finalise is unavailable.
 */
import {
  absDecimal,
  isZeroDecimal,
  parseMoney,
  subtractDecimals,
  sumDecimals,
  type AppLocale,
} from "@numo9/ui";

import type { Difference, Reason } from "./api";

export interface MeterRow {
  account: string;
  debit: string;
  credit: string;
}

export interface MeterTotals {
  debits: string;
  credits: string;
  /** debits − credits */
  difference: string;
  balanced: boolean;
  lines: number;
  unreadable: number;
}

function amount(text: string, locale: AppLocale): string | null {
  const trimmed = (text ?? "").trim();
  if (!trimmed) return "0.00";
  return parseMoney(trimmed, { locale });
}

export function meterTotals(rows: readonly MeterRow[], locale: AppLocale): MeterTotals {
  const debits: string[] = [];
  const credits: string[] = [];
  let unreadable = 0;
  let lines = 0;
  for (const row of rows) {
    if (!row.account) continue;
    const debit = amount(row.debit, locale);
    const credit = amount(row.credit, locale);
    if (debit === null || credit === null) unreadable += 1;
    if (debit && !isZeroDecimal(debit)) debits.push(debit);
    if (credit && !isZeroDecimal(credit)) credits.push(credit);
    if ((debit && !isZeroDecimal(debit)) || (credit && !isZeroDecimal(credit))) lines += 1;
  }
  const d = sumDecimals(debits);
  const c = sumDecimals(credits);
  const difference = subtractDecimals(d, c);
  return {
    debits: d,
    credits: c,
    difference,
    balanced: isZeroDecimal(difference),
    lines,
    unreadable,
  };
}

export type Blocker =
  | { kind: "finalised" }
  | { kind: "empty" }
  | { kind: "unreadable"; count: number }
  | { kind: "unbalanced"; difference: string }
  | { kind: "server"; reason: Reason };

/** Why Finalise is unavailable, the live totals first; an empty list: it can be finalised. */
export function blockers(
  totals: MeterTotals,
  server: Difference | null,
  finalised: boolean,
): Blocker[] {
  if (finalised) return [{ kind: "finalised" }];
  const out: Blocker[] = [];
  if (totals.lines === 0) out.push({ kind: "empty" });
  if (totals.unreadable) out.push({ kind: "unreadable", count: totals.unreadable });
  if (!totals.balanced) out.push({ kind: "unbalanced", difference: absDecimal(totals.difference) });
  const local = new Set(["conversion.unbalanced", "conversion.empty", "conversion.finalised"]);
  for (const reason of server?.reasons ?? []) {
    if (!local.has(reason.code)) out.push({ kind: "server", reason });
  }
  return out;
}
