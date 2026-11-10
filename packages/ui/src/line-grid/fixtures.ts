import { typeLabels } from "../pickers/fixtures";
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
