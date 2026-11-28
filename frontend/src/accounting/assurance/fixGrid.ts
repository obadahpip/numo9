/**
 * Editable grid of the proposed-fix drawer (K-09-T22): the proposal's lines as editable rows,
 * their totals and difference in exact cents, and the payload `POST …/fix` takes. A draft can be
 * created only when at least two lines carry an account and an amount and debits equal credits
 * (the journal screen's rule, C-04-T09); the server validates again (`assurance.fix.invalid`).
 */
import { isZeroDecimal, subtractDecimals, sumDecimals } from "@numo9/ui";

import type { Fix, FixLine } from "./api";

export interface GridLine {
  key: number;
  account: string;
  debit: string;
  credit: string;
  description: string;
}

let nextKey = 1;

export function emptyGridLine(): GridLine {
  return { key: nextKey++, account: "", debit: "", credit: "", description: "" };
}

const amount = (value: string) => (Number(value) ? value : "");

/** The proposal's lines as grid rows (zero amounts shown blank). */
export function gridFromFix(fix: Pick<Fix, "lines">): GridLine[] {
  return fix.lines.map((line: FixLine) => ({
    key: nextKey++,
    account: line.account,
    debit: amount(line.debit),
    credit: amount(line.credit),
    description: line.description,
  }));
}

const MONEY = /^\d{1,13}(\.\d{1,2})?$/;

/** An amount the grid accepts: empty, or a positive number with at most two decimals. */
export function validAmount(value: string): boolean {
  const text = value.trim();
  return text === "" || MONEY.test(text);
}

const filled = (line: GridLine) =>
  line.account !== "" && (Number(line.debit) > 0 || Number(line.credit) > 0);

export interface GridTotals {
  debit: string;
  credit: string;
  /** Debits − credits as a decimal string ("0.00" = balanced). */
  difference: string;
  balanced: boolean;
}

export function gridTotals(lines: readonly GridLine[]): GridTotals {
  const debit = sumDecimals(lines.map((l) => (validAmount(l.debit) ? l.debit.trim() : "")));
  const credit = sumDecimals(lines.map((l) => (validAmount(l.credit) ? l.credit.trim() : "")));
  const difference = subtractDecimals(debit, credit);
  return { debit, credit, difference, balanced: isZeroDecimal(difference) };
}

/** Why the draft can't be created yet, or `null` when it can. */
export function gridProblem(lines: readonly GridLine[]): "amount" | "lines" | "balance" | null {
  if (lines.some((l) => !validAmount(l.debit) || !validAmount(l.credit))) return "amount";
  if (lines.filter(filled).length < 2) return "lines";
  const totals = gridTotals(lines);
  if (!totals.balanced || isZeroDecimal(totals.debit)) return "balance";
  return null;
}

/** The lines `POST …/fix` takes: the filled rows only, blank amounts as 0. */
export function gridPayload(
  lines: readonly GridLine[],
): Pick<FixLine, "account" | "debit" | "credit" | "description">[] {
  return lines.filter(filled).map((line) => ({
    account: line.account,
    debit: line.debit.trim() || "0",
    credit: line.credit.trim() || "0",
    description: line.description.trim(),
  }));
}
