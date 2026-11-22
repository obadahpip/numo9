"use client";

import { formatMoney } from "../format/format";
import type { AppLocale } from "../format/locale";
import { cn } from "../primitives/cn";

export type DocumentDiscountType = "none" | "amount" | "percent";

export interface DocumentTotalsValue {
  subtotal: string;
  discountTotal: string;
  /** One row per tax component (GST/HST, PST, QST…), in the order given. */
  taxes: readonly { key: string; name: string; amount: string }[];
  taxTotal: string;
  total: string;
  /** Inclusive documents: the tax is part of the total ("Includes GST/HST $13.00"). */
  taxIncluded: boolean;
}

export interface DocumentTotalsLabels {
  /** Accessible name of the panel: "Totals". */
  region: string;
  subtotal: string;
  discount: string;
  discountType: string;
  discountNone: string;
  discountAmount: string;
  discountPercent: string;
  discountValue: string;
  total: string;
  /** (component, amount) → "Includes HST $13.00" (inclusive documents). */
  includes: (name: string, amount: string) => string;
  /** Read by screen readers when the total changes: (total) → "Total $214.70". */
  announce: (total: string) => string;
  /** Shown while the server's figures are on their way (the mirror's are on screen). */
  pending?: string;
}

export interface DocumentTotalsProps {
  value: DocumentTotalsValue;
  discountType: DocumentDiscountType;
  discountValue: string;
  onDiscountChange?: (type: DocumentDiscountType, value: string) => void;
  labels: DocumentTotalsLabels;
  locale: AppLocale;
  currency?: string;
  /** True while a recalculation is in flight. */
  pending?: boolean;
  readOnly?: boolean;
  className?: string;
}

/**
 * Totals panel of a document (D-01-T14): Subtotal, the document discount (amount or %, allocated
 * to the lines for tax by the calculator), tax per component (GST/HST, PST, QST — never one
 * lumped "Tax" line) and Total. The total is announced in a polite live region; the figures are
 * the server's (the client mirror's until the server answers).
 */
export function DocumentTotals({
  value,
  discountType,
  discountValue,
  onDiscountChange,
  labels,
  locale,
  currency = "CAD",
  pending = false,
  readOnly = false,
  className,
}: DocumentTotalsProps) {
  const money = (amount: string) => formatMoney(amount, { locale, currency });
  const row = "flex items-baseline justify-between gap-4 py-1";
  return (
    <section
      aria-label={labels.region}
      aria-busy={pending || undefined}
      className={cn(
        "w-full max-w-sm rounded-lg border border-border bg-surface p-4 text-sm",
        className,
      )}
    >
      <dl>
        <div className={row}>
          <dt>{labels.subtotal}</dt>
          <dd className="tabular-nums" data-total="subtotal">
            {money(value.subtotal)}
          </dd>
        </div>
        <div className={cn(row, "flex-wrap")}>
          <dt className="flex items-center gap-2">
            {labels.discount}
            {readOnly ? null : (
              <>
                <select
                  aria-label={labels.discountType}
                  value={discountType}
                  onChange={(event) =>
                    onDiscountChange?.(event.target.value as DocumentDiscountType, discountValue)
                  }
                  className="min-h-10 rounded-md border border-border bg-surface px-2 text-sm"
                >
                  <option value="none">{labels.discountNone}</option>
                  <option value="amount">{labels.discountAmount}</option>
                  <option value="percent">{labels.discountPercent}</option>
                </select>
                {discountType === "none" ? null : (
                  <input
                    aria-label={labels.discountValue}
                    inputMode="decimal"
                    autoComplete="off"
                    value={discountValue}
                    onChange={(event) => onDiscountChange?.(discountType, event.target.value)}
                    className="min-h-10 w-24 rounded-md border border-border bg-surface px-2 text-end text-sm tabular-nums"
                  />
                )}
              </>
            )}
          </dt>
          <dd className="tabular-nums" data-total="discount">
            {Number(value.discountTotal) ? `−${money(value.discountTotal)}` : money("0")}
          </dd>
        </div>
        {value.taxIncluded
          ? null
          : value.taxes.map((tax) => (
              <div key={tax.key} className={row}>
                <dt>{tax.name}</dt>
                <dd className="tabular-nums" data-total={`tax-${tax.key}`}>
                  {money(tax.amount)}
                </dd>
              </div>
            ))}
        <div className={cn(row, "mt-1 border-t border-border-strong pt-2 text-base font-bold")}>
          <dt>{labels.total}</dt>
          <dd className="tabular-nums" data-total="total">
            {money(value.total)}
          </dd>
        </div>
        {value.taxIncluded
          ? value.taxes.map((tax) => (
              <div key={tax.key} className={cn(row, "text-fg-muted")}>
                <dt className="sr-only">{tax.name}</dt>
                <dd data-total={`tax-${tax.key}`}>
                  {labels.includes(tax.name, money(tax.amount))}
                </dd>
              </div>
            ))
          : null}
      </dl>
      {pending && labels.pending ? (
        <p className="mt-2 text-xs text-fg-muted">{labels.pending}</p>
      ) : null}
      <p role="status" aria-live="polite" className="sr-only">
        {labels.announce(money(value.total))}
      </p>
    </section>
  );
}
