import { typeLabels } from "../pickers/fixtures";
import type { DocumentGridLine, DocumentLineAmounts, DocumentLinesLabels } from "./DocumentLines";
import type { JournalLine, JournalLinesLabels } from "./JournalLines";

/** Sample labels and lines for the LineGrid / JournalLines stories and tests. */
export const journalLabels: JournalLinesLabels = {
  grid: "Journal lines",
  addLine: "Add a line",
  removeLine: (n) => `Delete line ${n}`,
  moveLine: (n) => `Move line ${n} (drag, or Alt+↑/↓)`,
  cell: (column, n) => `${column}, line ${n}`,
  columns: "Columns",
  actions: "Actions",
  totals: "Totals",
  moved: (from, to) => `Line ${from} moved to position ${to}`,
  account: "Account",
  description: "Description",
  debit: "Debit",
  credit: "Credit",
  taxCode: "Tax code",
  noAccounts: "No accounts match.",
  accountTypes: typeLabels,
  balanced: "Balanced — debits equal credits.",
  unbalanced: (debits, credits, difference) =>
    `Debits (${debits}) and credits (${credits}) differ by ${difference}. Adjust a line so the difference is $0.00.`,
};

export const sampleJournal: JournalLine[] = [
  { id: "l1", account: "a1000", description: "Owner contribution", debit: "1250.00", credit: null },
  { id: "l2", account: "a3000", description: "Owner contribution", debit: null, credit: "1200.00" },
];

// ---- D-01: the document line editor -------------------------------------------------------------

export const documentLabels: DocumentLinesLabels = {
  ...journalLabels,
  grid: "Invoice lines",
  item: "Item",
  description: "Description",
  quantity: "Qty",
  unitPrice: "Unit price",
  discount: "Discount",
  account: "Account",
  taxCode: "Tax code",
  taxAmount: "Tax amount",
  amount: "Amount",
  noAccounts: "No accounts match.",
  noTaxCodes: "No tax codes match.",
  accountTypes: typeLabels,
  taxTypes: {
    taxable: "Taxable",
    zero_rated: "Zero-rated",
    exempt: "Exempt",
    out_of_scope: "Out of scope",
  },
  taxDefault: "Account default",
  taxOthers: "All codes",
  taxExpired: "Not in force on this date",
  duplicated: (n) => `Line ${n} duplicated`,
  lineRemoved: (n) => `Line ${n} deleted`,
  undo: "Undo",
  undoAlt: "Add the line again",
};

export const sampleDocumentLines: DocumentGridLine[] = [
  {
    id: "d1",
    item: "INSTALL",
    description: "Kitchen cabinets — install",
    quantity: "1",
    unitPrice: "4800.00",
    discount: "",
    account: "a4000",
    taxCode: "s-on",
  },
  {
    id: "d2",
    item: "",
    description: "Hardware",
    quantity: "24",
    unitPrice: "13.00",
    discount: "10%",
    account: "a4000",
    taxCode: "s-on",
  },
];

/** Story / test stand-in for the calculator (the app uses the DocumentCalculator mirror). */
export function roughAmounts(
  lines: readonly DocumentGridLine[],
  rates: Readonly<Record<string, string>>,
): Record<string, DocumentLineAmounts> {
  const out: Record<string, DocumentLineAmounts> = {};
  for (const line of lines) {
    const gross = Math.round(Number(line.quantity || "0") * Number(line.unitPrice || "0") * 100);
    const discount = line.discount.endsWith("%")
      ? Math.round((gross * Number(line.discount.slice(0, -1))) / 100)
      : Math.round(Number(line.discount || "0") * 100);
    const net = Math.max(gross - discount, 0);
    const tax = Math.round((net * Number(rates[line.taxCode ?? ""] ?? "0")) / 100);
    out[line.id] = { tax: (tax / 100).toFixed(2), amount: (net / 100).toFixed(2) };
  }
  return out;
}
