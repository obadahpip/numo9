"use client";

/** Translated labels of the shared document grid (D-01-T19). */
import type {
  DatePickerLabels,
  DocumentLinesLabels,
  DocumentTotalsLabels,
  DueDateFieldLabels,
} from "@numo9/ui";

import { useFormatMessage } from "@/i18n";

import { accountTypes, due, lines, taxTypes, totals } from "./messages";

export function useDocumentLinesLabels(side: "sales" | "purchase" = "sales"): DocumentLinesLabels {
  const fm = useFormatMessage();
  return {
    grid: fm(lines.grid),
    addLine: fm(lines.addLine),
    removeLine: (line) => fm(lines.removeLine, { line }),
    moveLine: (line) => fm(lines.moveLine, { line }),
    cell: (column, line) => fm(lines.cell, { column, line }),
    columns: fm(lines.columns),
    actions: fm(lines.actions),
    totals: fm(lines.totals),
    moved: (from, to) => fm(lines.moved, { from, to }),
    duplicated: (line) => fm(lines.duplicated, { line }),
    lineRemoved: (line) => fm(lines.lineRemoved, { line }),
    undo: fm(lines.undo),
    undoAlt: fm(lines.undoAlt),
    hiddenWithValues: (columns) => fm(lines.hiddenWithValues, { columns }),
    showHidden: fm(lines.showHidden),
    item: fm(lines.item),
    description: fm(lines.description),
    quantity: fm(lines.quantity),
    unitPrice: fm(side === "purchase" ? lines.unitCost : lines.unitPrice),
    discount: fm(lines.discount),
    account: fm(lines.account),
    taxCode: fm(lines.taxCode),
    taxAmount: fm(lines.taxAmount),
    amount: fm(lines.amount),
    noAccounts: fm(lines.noAccounts),
    noTaxCodes: fm(lines.noTaxCodes),
    accountTypes: {
      asset: fm(accountTypes.asset),
      liability: fm(accountTypes.liability),
      equity: fm(accountTypes.equity),
      revenue: fm(accountTypes.revenue),
      expense: fm(accountTypes.expense),
    },
    taxTypes: {
      taxable: fm(taxTypes.taxable),
      zero_rated: fm(taxTypes.zero_rated),
      exempt: fm(taxTypes.exempt),
      out_of_scope: fm(taxTypes.out_of_scope),
    },
    taxDefault: fm(lines.taxDefault),
    taxOthers: fm(lines.taxOthers),
    taxExpired: fm(lines.taxExpired),
    taxWhy: (line) => fm(lines.taxWhy, { line }),
    taxAuto: fm(lines.taxAuto),
    taxReset: (line) => fm(lines.taxReset, { line }),
  };
}

export function useDocumentTotalsLabels(): DocumentTotalsLabels {
  const fm = useFormatMessage();
  return {
    region: fm(totals.region),
    subtotal: fm(totals.subtotal),
    discount: fm(totals.discount),
    discountType: fm(totals.discountType),
    discountNone: fm(totals.discountNone),
    discountAmount: fm(totals.discountAmount),
    discountPercent: fm(totals.discountPercent),
    discountValue: fm(totals.discountValue),
    total: fm(totals.total),
    includes: (name, amount) => fm(totals.includes, { name, amount }),
    announce: (total) => fm(totals.announce, { total }),
    pending: fm(totals.pending),
  };
}

export function useDueDateLabels(date: DatePickerLabels): DueDateFieldLabels {
  const fm = useFormatMessage();
  return {
    label: fm(due.label),
    terms: fm(due.terms),
    dueIn: (days) => fm(due.dueIn, { days }),
    required: fm(due.required),
    beforeDate: fm(due.beforeDate),
    date,
  };
}
