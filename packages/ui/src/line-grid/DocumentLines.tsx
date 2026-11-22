"use client";

import type { AppLocale } from "../format/locale";
import { AccountPicker, type AccountType, type PickerAccount } from "../pickers/AccountPicker";
import {
  TaxCodePicker,
  type PickerTaxCode,
  type TaxCodeSide,
  type TaxCodeType,
} from "../pickers/TaxCodePicker";
import { useOptionalToast } from "../primitives/Toast";
import { LineGrid, type DocumentLine, type LineColumn, type LineGridLabels } from "./LineGrid";

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
  labels: DocumentLinesLabels;
  locale: AppLocale;
  currency?: string;
  readOnly?: boolean;
  defaultHiddenColumns?: string[];
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
  labels,
  locale,
  currency = "CAD",
  readOnly = false,
  defaultHiddenColumns = ["item", "discount"],
}: DocumentLinesProps) {
  const toast = useOptionalToast();
  const columns: LineColumn[] = [
    { id: "item", header: labels.item, kind: "text", width: 120, optional: true },
    { id: "description", header: labels.description, kind: "text" },
    {
      id: "quantity",
      header: labels.quantity,
      kind: "custom",
      width: 88,
      render: ({ id, label, value, onChange: set, onKeyDown }) => (
        <input
          id={id}
          aria-label={label}
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
      render: ({ id, label, value, onChange: set, onKeyDown }) => {
        const text = (value as string | undefined) ?? "";
        return (
          <input
            id={id}
            aria-label={label}
            aria-invalid={parseLineDiscount(text) === null || undefined}
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
          onKeyDownCapture={onKeyDown}
        />
      ),
    },
    {
      id: "taxCode",
      header: labels.taxCode,
      kind: "custom",
      width: 200,
      render: ({ id, label, value, onChange: set, onKeyDown }) => (
        <TaxCodePicker
          id={id}
          aria-label={label}
          codes={taxCodes}
          value={(value as string | null) ?? null}
          onChange={(codeId) => set(codeId)}
          side={side}
          date={date}
          typeLabels={labels.taxTypes}
          defaultLabel={labels.taxDefault}
          othersLabel={labels.taxOthers}
          expiredLabel={labels.taxExpired}
          emptyMessage={labels.noTaxCodes}
          disabled={readOnly}
          onKeyDownCapture={onKeyDown}
        />
      ),
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

  return (
    <LineGrid
      lines={shown}
      onChange={(next) => onChange(strip(next))}
      columns={columns}
      newLine={newDocumentLine}
      labels={labels}
      locale={locale}
      currency={currency}
      readOnly={readOnly}
      defaultHiddenColumns={defaultHiddenColumns}
      onLineRemoved={(_line, index, restore) =>
        toast?.toast({
          title: labels.lineRemoved(index + 1),
          undo: { label: labels.undo, altText: labels.undoAlt, onUndo: restore },
        })
      }
    />
  );
}
