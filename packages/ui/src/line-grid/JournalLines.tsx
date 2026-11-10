"use client";

import { compareDecimals, isZeroDecimal, subtractDecimals, absDecimal } from "../format/decimal";
import { formatMoney } from "../format/format";
import type { AppLocale } from "../format/locale";
import { AccountPicker, type AccountType, type PickerAccount } from "../pickers/AccountPicker";
import { cn } from "../primitives/cn";
import { LineGrid, type DocumentLine, type LineColumn, type LineGridLabels } from "./LineGrid";

/** A manual-journal line (C-02 posting engine input; C-04 full journal screen). */
export interface JournalLine extends DocumentLine {
  account: string | null;
  description: string;
  debit: string | null;
  credit: string | null;
  taxCode?: string | null;
}

export interface JournalLinesLabels extends LineGridLabels {
  account: string;
  description: string;
  debit: string;
  credit: string;
  taxCode: string;
  noAccounts: string;
  accountTypes: Record<AccountType, string>;
  /** Balanced: e.g. "Balanced". */
  balanced: string;
  /** Unbalanced, with formatted amounts (microcopy §3.5): (debits, credits, difference) → text. */
  unbalanced: (debits: string, credits: string, difference: string) => string;
}

let lineCounter = 0;
export function newJournalLine(): JournalLine {
  lineCounter += 1;
  return {
    id: `line-${Date.now().toString(36)}-${lineCounter}`,
    account: null,
    description: "",
    debit: null,
    credit: null,
    taxCode: null,
  };
}

export interface JournalBalance {
  debits: string;
  credits: string;
  difference: string;
  balanced: boolean;
}

/** Debits, credits and whether they balance (exact decimals). Empty journals don't balance. */
export function journalBalance(
  lines: readonly JournalLine[],
  totals?: Record<string, string>,
): JournalBalance {
  const debits = totals?.debit ?? "0.00";
  const credits = totals?.credit ?? "0.00";
  const difference = subtractDecimals(debits, credits);
  const used = lines.some((line) => line.debit || line.credit);
  return { debits, credits, difference, balanced: used && compareDecimals(debits, credits) === 0 };
}

export interface JournalLinesProps {
  lines: JournalLine[];
  onChange: (lines: JournalLine[]) => void;
  accounts: readonly PickerAccount[];
  labels: JournalLinesLabels;
  locale: AppLocale;
  readOnly?: boolean;
}

/**
 * Journal line editor (A-10-T11): `LineGrid` with Account · Description · Debit · Credit (and an
 * optional Tax code column). A line holds a debit or a credit, never both — typing one clears the
 * other. The balance indicator turns green at a $0.00 difference; until then it names both totals
 * and the difference (microcopy §3.5: "Debits ($1,250.00) and credits ($1,200.00) differ by
 * $50.00.").
 */
export function JournalLines({
  lines,
  onChange,
  accounts,
  labels,
  locale,
  readOnly = false,
}: JournalLinesProps) {
  const columns: LineColumn[] = [
    {
      id: "account",
      header: labels.account,
      kind: "custom",
      width: 260,
      render: ({ id, label, value, onChange: set, onKeyDown }) => (
        <AccountPicker
          id={id}
          aria-label={label}
          accounts={accounts}
          value={(value as string | null) ?? null}
          onChange={(accountId) => set(accountId)}
          typeLabels={labels.accountTypes}
          emptyMessage={labels.noAccounts}
          disabled={readOnly}
          // The grid's ↑/↓/Enter navigation applies while the account list is closed.
          onKeyDownCapture={onKeyDown}
        />
      ),
    },
    { id: "description", header: labels.description, kind: "text" },
    { id: "taxCode", header: labels.taxCode, kind: "text", optional: true, width: 120 },
    { id: "debit", header: labels.debit, kind: "money", total: true, width: 140 },
    { id: "credit", header: labels.credit, kind: "money", total: true, width: 140 },
  ];

  const change = (next: DocumentLine[]) => {
    // Debit and credit are exclusive: the side just entered wins.
    const cleaned = (next as JournalLine[]).map((line, i) => {
      const before = lines.find((l) => l.id === line.id) ?? lines[i];
      if (line.debit && line.credit) {
        return before?.debit === line.debit ? { ...line, debit: null } : { ...line, credit: null };
      }
      return line;
    });
    onChange(cleaned);
  };

  return (
    <LineGrid
      lines={lines}
      onChange={change}
      columns={columns}
      newLine={newJournalLine}
      labels={labels}
      locale={locale}
      minLines={2}
      defaultHiddenColumns={["taxCode"]}
      readOnly={readOnly}
      footer={(totals) => {
        const balance = journalBalance(lines, totals);
        const money = (value: string) => formatMoney(value, { locale });
        return (
          <p
            role="status"
            data-balanced={balance.balanced}
            className={cn(
              "rounded-md px-3 py-2 text-sm font-semibold",
              balance.balanced
                ? "bg-surface-success-subtle text-fg-success"
                : "bg-surface-warning-subtle text-fg-warning",
            )}
          >
            {balance.balanced || isZeroDecimal(balance.difference)
              ? labels.balanced
              : labels.unbalanced(
                  money(balance.debits),
                  money(balance.credits),
                  money(absDecimal(balance.difference)),
                )}
          </p>
        );
      }}
    />
  );
}
