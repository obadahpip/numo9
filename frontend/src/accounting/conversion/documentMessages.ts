import { defineMessages } from "@/i18n";

/** Open invoices / bills grids of the conversion (C-05-T12). */
export const dm = defineMessages({
  invoicesIntro: {
    id: "conversion.documents.invoicesIntro",
    defaultMessage:
      "Enter each customer invoice still open at the conversion date — or paste the rows from a spreadsheet (customer, number, date, due date, total, still owed). They are aged, reminded and paid like any invoice; their total must equal the Accounts receivable balance.",
    description: "Open invoices step text",
  },
  billsIntro: {
    id: "conversion.documents.billsIntro",
    defaultMessage:
      "Enter each supplier bill still unpaid at the conversion date — or paste the rows from a spreadsheet (supplier, supplier's invoice number, date, due date, total, still owed). Their total must equal the Accounts payable balance.",
    description: "Open bills step text",
  },
  grid: {
    id: "conversion.documents.grid",
    defaultMessage: "{kind, select, bill {Open bills to add} other {Open invoices to add}}",
    description: "Accessible name of the entry grid",
  },
  saved: {
    id: "conversion.documents.saved",
    defaultMessage: "{kind, select, bill {Open bills entered} other {Open invoices entered}}",
    description: "Caption of the saved documents table",
  },
  contact: {
    id: "conversion.documents.contact",
    defaultMessage: "{kind, select, bill {Supplier} other {Customer}}",
    description: "Column",
  },
  number: {
    id: "conversion.documents.number",
    defaultMessage: "{kind, select, bill {Supplier's invoice no.} other {Invoice no.}}",
    description: "Column",
  },
  date: { id: "conversion.documents.date", defaultMessage: "Date", description: "Column" },
  dueDate: {
    id: "conversion.documents.dueDate",
    defaultMessage: "Due date",
    description: "Column",
  },
  total: { id: "conversion.documents.total", defaultMessage: "Total", description: "Column" },
  outstanding: {
    id: "conversion.documents.outstanding",
    defaultMessage: "Still owed",
    description: "Column: what was still owed at the conversion date",
  },
  reference: {
    id: "conversion.documents.reference",
    defaultMessage: "Reference",
    description: "Column",
  },
  cell: {
    id: "conversion.documents.cell",
    defaultMessage: "{column}, row {row}",
    description: "Accessible name of a cell",
  },
  addRow: { id: "conversion.documents.addRow", defaultMessage: "Add a row", description: "Button" },
  removeRow: {
    id: "conversion.documents.removeRow",
    defaultMessage: "Remove row {row}",
    description: "Button (accessible name)",
  },
  check: {
    id: "conversion.documents.check",
    defaultMessage: "Verify the rows",
    description: "Button: validate without saving",
  },
  add: {
    id: "conversion.documents.add",
    defaultMessage: "{count, plural, one {Add # document} other {Add # documents}}",
    description: "Button",
  },
  pasted: {
    id: "conversion.documents.pasted",
    defaultMessage: "{count, plural, one {# row pasted} other {# rows pasted}}.",
    description: "Announcement after a paste",
  },
  valid: {
    id: "conversion.documents.valid",
    defaultMessage: "{count, plural, one {# row is ready} other {All # rows are ready}} to add.",
    description: "Result of the check",
  },
  invalid: {
    id: "conversion.documents.invalid",
    defaultMessage:
      "{count, plural, one {# row has a problem} other {# rows have problems}}: nothing was added. Fix them and try again.",
    description: "Result of the check or the save",
  },
  added: {
    id: "conversion.documents.added",
    defaultMessage: "{count, plural, one {# document added} other {# documents added}}.",
    description: "Result of the save",
  },
  rowProblem: {
    id: "conversion.documents.rowProblem",
    defaultMessage: "Row {row}: {message}",
    description: "A row's problem",
  },
  none: {
    id: "conversion.documents.none",
    defaultMessage: "None entered yet.",
    description: "Empty saved list",
  },
  remove: { id: "conversion.documents.remove", defaultMessage: "Remove", description: "Button" },
  removeNamed: {
    id: "conversion.documents.removeNamed",
    defaultMessage: "Remove {number}",
    description: "Button (accessible name)",
  },
  totalOwed: {
    id: "conversion.documents.totalOwed",
    defaultMessage: "{count, plural, one {# document} other {# documents}} · still owed {amount}",
    description: "Footer of the saved list",
  },
  failed: {
    id: "conversion.documents.failed",
    defaultMessage: "That didn't work and nothing was changed. Try again in a moment.",
    description: "Error",
  },
});
