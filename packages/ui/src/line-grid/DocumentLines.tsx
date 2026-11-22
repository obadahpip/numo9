"use client";

import { useState } from "react";

import type { AppLocale } from "../format/locale";
import { parseMoney } from "../format/parse";
import {
  AccountPicker,
  allowedInContext,
  type AccountType,
  type PickerAccount,
} from "../pickers/AccountPicker";
import {
  TaxCodePicker,
  taxCodeOffered,
  type PickerTaxCode,
  type TaxCodeSide,
  type TaxCodeType,
} from "../pickers/TaxCodePicker";
import { useOptionalToast } from "../primitives/Toast";
import { Tooltip } from "../primitives/Tooltip";
import {
  LineGrid,
  type ColumnStore,
  type DocumentLine,
  type LineColumn,
  type LineGridLabels,
} from "./LineGrid";

/** A line of a sales or purchase document (D-01): what the person types. */
export interface DocumentGridLine extends DocumentLine {
  item: string;
  description: string;
  /** Decimal string, up to 4 decimals. */
  quantity: string;
  unitPrice: string | null;
  /** "10%" (percent) or "5.00" (amount); empty: none. */
  discount: string;
  account: string | null;
  taxCode: string | null;
}

/** The server's (or the mirror's) figures for a line: shown in Tax amount and Amount. */
export interface DocumentLineAmounts {
  tax: string;
  amount: string;
}

export interface DocumentLinesLabels extends LineGridLabels {
  item: string;
  description: string;
  quantity: string;
  unitPrice: string;
  discount: string;
  account: string;
  taxCode: string;
  taxAmount: string;
  amount: string;
  noAccounts: string;
  noTaxCodes: string;
  accountTypes: Record<AccountType, string>;
  taxTypes: Record<TaxCodeType, string>;
  taxDefault: string;
  taxOthers: string;
  taxExpired: string;
  /** Accessible name of the "why this tax" button: (line) → "Why this tax code, line 2". */
  taxWhy: (line: number) => string;
  duplicated: (line: number) => string;
  /** Undo toast after a delete: (line) → "Line 3 deleted". */
  lineRemoved: (line: number) => string;
  undo: string;
  /** How else to undo, for screen readers: "Add the line again". */
  undoAlt: string;
}

export interface DocumentLinesProps {
  lines: DocumentGridLine[];
  onChange: (lines: DocumentGridLine[]) => void;
  side: TaxCodeSide;
  /** Document date (YYYY-MM-DD). */
  date: string;
  accounts: readonly PickerAccount[];
  taxCodes: readonly PickerTaxCode[];
  /** Figures per line id (Tax amount, Amount). */
  amounts?: Readonly<Record<string, DocumentLineAmounts>>;
  /** Why a line has its tax code, per line id: "Ontario customer → HST 13 %" (D-01-T12, G-02). */
  taxWhy?: Readonly<Record<string, string>>;
  /** Each line account's default tax code key (G-01-T09), listed first in the tax picker. */
  accountDefaults?: Readonly<Record<string, string>>;
  labels: DocumentLinesLabels;
  locale: AppLocale;
  currency?: string;
  readOnly?: boolean;
  defaultHiddenColumns?: string[];
  /** Keeps the person's column choice (`localColumnStore("numo9.lines.<user>.sales")`). */
  columnStore?: ColumnStore;
}

let counter = 0;
export function newDocumentLine(): DocumentGridLine {
  counter += 1;
  return {
    id: `doc-line-${Date.now().toString(36)}-${counter}`,
    item: "",
    description: "",
    quantity: "1",
    unitPrice: null,
    discount: "",
    account: null,
    taxCode: null,
  };
}

/** "10%" → percent 10; "5" / "5.00" → amount 5.00; "" → none. Unreadable → null. */
export function parseLineDiscount(
  text: string,
): { type: "none" | "amount" | "percent"; value: string } | null {
  const raw = text.trim().replace(/\s/g, "").replace(",", ".");
  if (!raw) return { type: "none", value: "0" };
  const percent = raw.endsWith("%");
  const number = percent ? raw.slice(0, -1) : raw.replace(/^\$/, "");
  if (!/^\d+(\.\d{1,4})?$/.test(number)) return null;
  if (percent && Number(number) > 100) return null;
  return { type: percent ? "percent" : "amount", value: number };
}

const DECIMAL = /^-?\d+(\.\d{1,4})?$/;

/** Find a pasted account by code, then by name (case-insensitive), among those the side allows. */
function matchAccount(
  text: string,
  accounts: readonly PickerAccount[],
  side: TaxCodeSide,
): string | null {
  const wanted = text.trim().toLowerCase();
  const usable = accounts.filter((a) => allowedInContext(a, side) && a.postable !== false);
  const found =
    usable.find((a) => a.code.toLowerCase() === wanted) ??
    usable.find((a) => a.name.toLowerCase() === wanted) ??
    usable.find((a) => `${a.code} ${a.name}`.toLowerCase() === wanted);
  return found?.id ?? null;
}

/** Find a pasted tax code by key, name or detail, among those offered on the side and date. */
function matchTaxCode(
  text: string,
  codes: readonly PickerTaxCode[],
  side: TaxCodeSide,
  date: string,
): string | null {
  const wanted = text.trim().toLowerCase();
  const usable = codes.filter((c) => taxCodeOffered(c, side, date));
  const found = usable.find((c) =>
    [c.code, c.name, c.detail ?? ""].some((v) => v.toLowerCase() === wanted),
  );
  return found?.id ?? null;
}

export interface PastedLines {
  lines: DocumentGridLine[];
  /** Cells that didn't fit, per line id. */
  invalid: Record<string, string[]>;
}

/**
 * Spreadsheet rows pasted at `start` into `columns` (D-01-T15): each cell is read for its column —
 * quantity and discount as numbers, unit price as an amount (forgiving: "$1,200.50"), account by
 * code or name and tax code by key, name or rates, only among those the side and date allow.
 * Rows overwrite the lines from `start` down and add lines past the end. A cell that doesn't fit
 * keeps its text where it can (description, quantity, discount) and is flagged.
 */
export function pasteRows(
  rows: readonly string[][],
  start: number,
  columns: readonly string[],
  current: readonly DocumentGridLine[],
  context: {
    side: TaxCodeSide;
    date: string;
    accounts: readonly PickerAccount[];
    taxCodes: readonly PickerTaxCode[];
    locale: AppLocale;
  },
): PastedLines {
  const lines = [...current];
  const invalid: Record<string, string[]> = {};
  rows.forEach((cells, offset) => {
    const at = start + offset;
    const line: DocumentGridLine = { ...(lines[at] ?? newDocumentLine()) };
    const bad: string[] = [];
    columns.forEach((column, i) => {
      const raw = cells[i];
      if (raw === undefined) return;
      const text = raw.trim();
      switch (column) {
        case "item":
          line.item = text;
          break;
        case "description":
          line.description = raw;
          break;
        case "quantity":
          line.quantity = text.replace(",", ".");
          if (text && !DECIMAL.test(line.quantity)) bad.push(column);
          break;
        case "unitPrice": {
          const amount = text
            ? parseMoney(text, { locale: context.locale, fractionDigits: 4 })
            : null;
          line.unitPrice = amount;
          if (text && amount === null) bad.push(column);
          break;
        }
        case "discount":
          line.discount = text;
          if (parseLineDiscount(text) === null) bad.push(column);
          break;
        case "account":
          line.account = text ? matchAccount(text, context.accounts, context.side) : null;
          if (text && line.account === null) bad.push(column);
          break;
        case "taxCode":
          line.taxCode = text
            ? matchTaxCode(text, context.taxCodes, context.side, context.date)
            : null;
          if (text && line.taxCode === null) bad.push(column);
          break;
        default:
          break; // calculated columns: pasted values are ignored
      }
    });
    lines[at] = line;
    if (bad.length) invalid[line.id] = bad;
  });
  return { lines, invalid };
}

/**
 * Document line editor (D-01-T11): `LineGrid` configured for invoices, quotes, credit notes and
 * (E-02) bills — Item · Description · Qty · Unit price · Discount · Account · Tax code · Tax amount
 * · Amount. Tax amount and Amount are calculated (server-authoritative, shown from `amounts`).
 * Keyboard as LineGrid, plus Ctrl+D duplicate and Ctrl+Backspace delete with an Undo toast.
 */
export function DocumentLines({
  lines,
  onChange,
  side,
  date,
  accounts,
  taxCodes,
  amounts = {},
  taxWhy = {},
  accountDefaults = {},
  labels,
  locale,
  currency = "CAD",
  readOnly = false,
  defaultHiddenColumns = ["item", "discount"],
  columnStore,
}: DocumentLinesProps) {
  const toast = useOptionalToast();
  const [invalid, setInvalid] = useState<Record<string, string[]>>({});
  const columns: LineColumn[] = [
    { id: "item", header: labels.item, kind: "text", width: 120, optional: true },
    { id: "description", header: labels.description, kind: "text" },
    {
      id: "quantity",
      header: labels.quantity,
      kind: "custom",
      width: 88,
      render: ({ id, label, value, onChange: set, onKeyDown, invalid: bad }) => (
        <input
          id={id}
          aria-label={label}
          aria-invalid={bad || undefined}
          inputMode="decimal"
          autoComplete="off"
          value={(value as string | undefined) ?? ""}
          readOnly={readOnly}
          onChange={(event) => set(event.target.value)}
          onKeyDown={onKeyDown}
          className="min-h-10 w-full rounded-sm border border-transparent bg-transparent px-2 text-end text-sm text-fg tabular-nums hover:border-border focus:border-border-strong focus:bg-surface"
        />
      ),
    },
    { id: "unitPrice", header: labels.unitPrice, kind: "money", width: 120 },
    {
      id: "discount",
      header: labels.discount,
      kind: "custom",
      width: 96,
      optional: true,
      render: ({ id, label, value, onChange: set, onKeyDown, invalid: bad }) => {
        const text = (value as string | undefined) ?? "";
        return (
          <input
            id={id}
            aria-label={label}
            aria-invalid={bad || parseLineDiscount(text) === null || undefined}
            autoComplete="off"
            value={text}
            readOnly={readOnly}
            placeholder="0%"
            onChange={(event) => set(event.target.value)}
            onKeyDown={onKeyDown}
            className="min-h-10 w-full rounded-sm border border-transparent bg-transparent px-2 text-end text-sm text-fg tabular-nums hover:border-border focus:border-border-strong focus:bg-surface aria-invalid:border-border-danger"
          />
        );
      },
    },
    {
      id: "account",
      header: labels.account,
      kind: "custom",
      width: 220,
      render: ({ id, label, value, onChange: set, onKeyDown, invalid: bad }) => (
        <AccountPicker
          id={id}
          aria-label={label}
          aria-invalid={bad || undefined}
          accounts={accounts}
          // Sales lines: revenue, other income, deposits — never an expense account (gap-07);
          // purchase lines: expenses and the assets a bill buys. Same rules as the server.
          context={side}
          value={(value as string | null) ?? null}
          onChange={(accountId) => set(accountId)}
          typeLabels={labels.accountTypes}
          emptyMessage={labels.noAccounts}
          disabled={readOnly}
          onKeyDownCapture={onKeyDown}
        />
      ),
    },
    {
      id: "taxCode",
      header: labels.taxCode,
      kind: "custom",
      width: 200,
      render: ({ id, label, value, onChange: set, onKeyDown, line, index, invalid: bad }) => {
        const why = taxWhy[line.id];
        const account = (line as DocumentGridLine).account;
        return (
          <div className="flex items-start gap-1">
            <div className="min-w-0 flex-1">
              <TaxCodePicker
                id={id}
                aria-label={label}
                aria-invalid={bad || undefined}
                codes={taxCodes}
                value={(value as string | null) ?? null}
                onChange={(codeId) => set(codeId)}
                // Only this side's codes, in force on the document date (gap-07, G-01-T08).
                side={side}
                date={date}
                accountDefault={account ? (accountDefaults[account] ?? null) : null}
                typeLabels={labels.taxTypes}
                defaultLabel={labels.taxDefault}
                othersLabel={labels.taxOthers}
                expiredLabel={labels.taxExpired}
                emptyMessage={labels.noTaxCodes}
                disabled={readOnly}
                onKeyDownCapture={onKeyDown}
              />
            </div>
            {why ? (
              <Tooltip content={why}>
                <button
                  type="button"
                  aria-label={labels.taxWhy(index + 1)}
                  aria-description={why}
                  tabIndex={-1}
                  data-tax-why=""
                  className="mt-2 inline-flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-fg-muted hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-border-focus"
                >
                  <span aria-hidden="true">?</span>
                </button>
              </Tooltip>
            ) : null}
          </div>
        );
      },
    },
    {
      id: "taxAmount",
      header: labels.taxAmount,
      kind: "money",
      width: 112,
      readOnly: true,
      total: true,
    },
    { id: "amount", header: labels.amount, kind: "money", width: 128, readOnly: true, total: true },
  ];

  const shown = lines.map((line) => ({
    ...line,
    taxAmount: amounts[line.id]?.tax ?? null,
    amount: amounts[line.id]?.amount ?? null,
  }));

  const strip = (next: DocumentLine[]): DocumentGridLine[] =>
    next.map((line) => {
      const { taxAmount: _tax, amount: _amount, ...rest } = line;
      return rest as DocumentGridLine;
    });

  const change = (next: DocumentLine[]) => {
    const stripped = strip(next);
    // A flagged cell the person edits is no longer flagged.
    setInvalid((flags) => {
      const kept: Record<string, string[]> = {};
      for (const line of stripped) {
        const before = lines.find((l) => l.id === line.id);
        const left = (flags[line.id] ?? []).filter(
          (column) => before && before[column] === line[column],
        );
        if (left.length) kept[line.id] = left;
      }
      return kept;
    });
    onChange(stripped);
  };

  return (
    <LineGrid
      lines={shown}
      onChange={change}
      invalidCells={invalid}
      onPasteRows={
        readOnly
          ? undefined
          : (rows, start, cols) => {
              const pasted = pasteRows(rows, start, cols, lines, {
                side,
                date,
                accounts,
                taxCodes,
                locale,
              });
              onChange(pasted.lines);
              setInvalid((flags) => ({ ...flags, ...pasted.invalid }));
            }
      }
      columns={columns}
      newLine={newDocumentLine}
      labels={labels}
      locale={locale}
      currency={currency}
      readOnly={readOnly}
      defaultHiddenColumns={defaultHiddenColumns}
      columnStore={columnStore}
      onLineRemoved={(_line, index, restore) =>
        toast?.toast({
          title: labels.lineRemoved(index + 1),
          undo: { label: labels.undo, altText: labels.undoAlt, onUndo: restore },
        })
      }
    />
  );
}
