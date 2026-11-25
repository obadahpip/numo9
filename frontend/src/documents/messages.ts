import { defineMessages } from "@/i18n";

/** The shared document grid (D-01-T19): line editor, totals panel, due date. */
export const lines = defineMessages({
  grid: {
    id: "documents.lines.grid",
    defaultMessage: "Lines",
    description: "Accessible name of the document lines table",
  },
  addLine: {
    id: "documents.lines.addLine",
    defaultMessage: "Add a line",
    description: "Button under the lines",
  },
  removeLine: {
    id: "documents.lines.removeLine",
    defaultMessage: "Delete line {line}",
    description: "Delete button of a line",
  },
  moveLine: {
    id: "documents.lines.moveLine",
    defaultMessage: "Move line {line} (drag, or Alt+↑/↓)",
    description: "Drag handle of a line",
  },
  cell: {
    id: "documents.lines.cell",
    defaultMessage: "{column}, line {line}",
    description: "Accessible name of a cell",
  },
  columns: {
    id: "documents.lines.columns",
    defaultMessage: "Columns",
    description: "Column chooser button",
  },
  actions: {
    id: "documents.lines.actions",
    defaultMessage: "Actions",
    description: "Header of the delete column (screen readers)",
  },
  totals: {
    id: "documents.lines.totals",
    defaultMessage: "Totals",
    description: "Footer row of the lines",
  },
  moved: {
    id: "documents.lines.moved",
    defaultMessage: "Line {from} moved to position {to}",
    description: "Announced after a reorder",
  },
  duplicated: {
    id: "documents.lines.duplicated",
    defaultMessage: "Line {line} duplicated",
    description: "Announced after Ctrl+D",
  },
  lineRemoved: {
    id: "documents.lines.lineRemoved",
    defaultMessage: "Line {line} deleted",
    description: "Toast after deleting a line",
  },
  undo: { id: "documents.lines.undo", defaultMessage: "Undo", description: "Toast action" },
  undoAlt: {
    id: "documents.lines.undoAlt",
    defaultMessage: "Add the line again",
    description: "How else to undo (screen readers)",
  },
  hiddenWithValues: {
    id: "documents.lines.hiddenWithValues",
    defaultMessage: "Hidden columns with values: {columns}.",
    description: "Note when hidden columns hold values",
  },
  showHidden: {
    id: "documents.lines.showHidden",
    defaultMessage: "Show",
    description: "Button: show the hidden columns that hold values",
  },
  item: { id: "documents.lines.item", defaultMessage: "Item", description: "Column" },
  description: {
    id: "documents.lines.description",
    defaultMessage: "Description",
    description: "Column",
  },
  quantity: {
    id: "documents.lines.quantity",
    defaultMessage: "Qty",
    description: "Column: quantity",
  },
  unitPrice: {
    id: "documents.lines.unitPrice",
    defaultMessage: "Unit price",
    description: "Column",
  },
  unitCost: {
    id: "documents.lines.unitCost",
    defaultMessage: "Unit cost",
    description: "Column on purchase documents",
  },
  discount: {
    id: "documents.lines.discount",
    defaultMessage: "Discount",
    description: "Column: line discount, amount or %",
  },
  account: { id: "documents.lines.account", defaultMessage: "Account", description: "Column" },
  taxCode: { id: "documents.lines.taxCode", defaultMessage: "Tax code", description: "Column" },
  taxAmount: {
    id: "documents.lines.taxAmount",
    defaultMessage: "Tax amount",
    description: "Column",
  },
  amount: { id: "documents.lines.amount", defaultMessage: "Amount", description: "Column" },
  noAccounts: {
    id: "documents.lines.noAccounts",
    defaultMessage: "No accounts match.",
    description: "Account picker, nothing found",
  },
  noTaxCodes: {
    id: "documents.lines.noTaxCodes",
    defaultMessage: "No tax codes match.",
    description: "Tax picker, nothing found",
  },
  taxDefault: {
    id: "documents.lines.taxDefault",
    defaultMessage: "Account default",
    description: "Tax picker group: the account's default code",
  },
  taxOthers: {
    id: "documents.lines.taxOthers",
    defaultMessage: "All codes",
    description: "Tax picker group",
  },
  taxExpired: {
    id: "documents.lines.taxExpired",
    defaultMessage: "Not in force on this date",
    description: "Under a tax code that ended before the document date",
  },
  taxWhy: {
    id: "documents.lines.taxWhy",
    defaultMessage: "Why this tax code, line {line}",
    description: "Button with the reason for the line's tax code",
  },
  taxAuto: {
    id: "documents.lines.taxAuto",
    defaultMessage: "auto",
    description: "Chip: the line's tax code is the default (G-02-T07)",
  },
  taxReset: {
    id: "documents.lines.taxReset",
    defaultMessage: "Changed from the default, line {line}: reset to the default",
    description: "Override dot button (G-02-T07)",
  },
});

export const accountTypes = defineMessages({
  asset: {
    id: "documents.lines.accountTypes.asset",
    defaultMessage: "Assets",
    description: "Account picker group",
  },
  liability: {
    id: "documents.lines.accountTypes.liability",
    defaultMessage: "Liabilities",
    description: "Account picker group",
  },
  equity: {
    id: "documents.lines.accountTypes.equity",
    defaultMessage: "Equity",
    description: "Account picker group",
  },
  revenue: {
    id: "documents.lines.accountTypes.revenue",
    defaultMessage: "Revenue",
    description: "Account picker group",
  },
  expense: {
    id: "documents.lines.accountTypes.expense",
    defaultMessage: "Expenses",
    description: "Account picker group",
  },
});

export const taxTypes = defineMessages({
  taxable: {
    id: "documents.lines.taxTypes.taxable",
    defaultMessage: "Taxable",
    description: "Tax code type badge",
  },
  zero_rated: {
    id: "documents.lines.taxTypes.zeroRated",
    defaultMessage: "Zero-rated",
    description: "Tax code type badge",
  },
  exempt: {
    id: "documents.lines.taxTypes.exempt",
    defaultMessage: "Exempt",
    description: "Tax code type badge",
  },
  out_of_scope: {
    id: "documents.lines.taxTypes.outOfScope",
    defaultMessage: "Out of scope",
    description: "Tax code type badge",
  },
});

export const totals = defineMessages({
  region: {
    id: "documents.totals.region",
    defaultMessage: "Totals",
    description: "Accessible name of the totals panel",
  },
  subtotal: {
    id: "documents.totals.subtotal",
    defaultMessage: "Subtotal",
    description: "Totals row",
  },
  discount: {
    id: "documents.totals.discount",
    defaultMessage: "Discount",
    description: "Totals row: the document discount",
  },
  discountType: {
    id: "documents.totals.discountType",
    defaultMessage: "Discount type",
    description: "Select: none, amount or percent",
  },
  discountNone: {
    id: "documents.totals.discountNone",
    defaultMessage: "None",
    description: "Discount type option",
  },
  discountAmount: {
    id: "documents.totals.discountAmount",
    defaultMessage: "Amount",
    description: "Discount type option",
  },
  discountPercent: {
    id: "documents.totals.discountPercent",
    defaultMessage: "Percent",
    description: "Discount type option",
  },
  discountValue: {
    id: "documents.totals.discountValue",
    defaultMessage: "Discount value",
    description: "Input: the discount amount or percent",
  },
  total: { id: "documents.totals.total", defaultMessage: "Total", description: "Totals row" },
  includes: {
    id: "documents.totals.includes",
    defaultMessage: "Includes {name} {amount}",
    description: "Tax-inclusive document: the tax in the total",
  },
  announce: {
    id: "documents.totals.announce",
    defaultMessage: "Total {total}",
    description: "Read by screen readers when the total changes",
  },
  pending: {
    id: "documents.totals.pending",
    defaultMessage: "Updating…",
    description: "While the server recalculates",
  },
});

export const due = defineMessages({
  label: { id: "documents.due.label", defaultMessage: "Due date", description: "Field label" },
  terms: {
    id: "documents.due.terms",
    defaultMessage: "Payment terms",
    description: "Group of term chips",
  },
  dueIn: {
    id: "documents.due.dueIn",
    defaultMessage:
      "{days, plural, =0 {Due on the document date} one {Due in # day} other {Due in # days}}",
    description: "Helper under the due date",
  },
  required: {
    id: "documents.due.required",
    defaultMessage: "Enter a due date.",
    description: "Error: saving without a due date",
  },
  beforeDate: {
    id: "documents.due.beforeDate",
    defaultMessage: "The due date is before the document date.",
    description: "Error",
  },
});
