import { defineMessages, type MessageDescriptor } from "@/i18n";

import type { LineStatus, Role, Sign } from "./api";

/** Statement import wizard (F-02-T12). */
export const imp = defineMessages({
  title: {
    id: "banking.import.title",
    defaultMessage: "Import a statement",
    description: "Page heading of the statement import wizard",
  },
  intro: {
    id: "banking.import.intro",
    defaultMessage:
      "Bring in the lines of your bank's statement file. Nothing is imported until you confirm.",
    description: "Text under the import wizard heading",
  },
  back: {
    id: "banking.import.back",
    defaultMessage: "Back to the account",
    description: "Link from the import wizard to the bank account page",
  },
  steps: { id: "banking.import.steps", defaultMessage: "Import steps", description: "Stepper" },
  stepUpload: { id: "banking.import.stepUpload", defaultMessage: "Upload", description: "Step" },
  stepMap: { id: "banking.import.stepMap", defaultMessage: "Map", description: "Step" },
  stepPreview: { id: "banking.import.stepPreview", defaultMessage: "Preview", description: "Step" },
  stepConfirm: { id: "banking.import.stepConfirm", defaultMessage: "Confirm", description: "Step" },
  stepItem: {
    id: "banking.import.stepItem",
    defaultMessage: "{n}. {name}",
    description: "One step of the stepper: number and name",
  },
  dropTitle: {
    id: "banking.import.dropTitle",
    defaultMessage: "Drop your statement file here",
    description: "Drag-and-drop zone",
  },
  chooseFile: {
    id: "banking.import.chooseFile",
    defaultMessage: "Choose a file",
    description: "Button opening the file picker",
  },
  dropHelp: {
    id: "banking.import.dropHelp",
    defaultMessage: "CSV, Excel (.xlsx), OFX, QFX or QBO — up to 25 MB.",
    description: "Accepted files, under the drop zone",
  },
  formatsTitle: {
    id: "banking.import.formatsTitle",
    defaultMessage: "Where to find the file",
    description: "Heading of the sample-format help",
  },
  formatsCsv: {
    id: "banking.import.formatsCsv",
    defaultMessage:
      "CSV or Excel: in your online banking, open the account's transactions and choose Download. RBC, TD, Scotiabank, BMO, CIBC, Desjardins, National Bank and Tangerine files are recognised by themselves.",
    description: "Sample-format help: spreadsheet files",
  },
  formatsOfx: {
    id: "banking.import.formatsOfx",
    defaultMessage:
      "OFX, QFX or QBO (Money, Quicken or QuickBooks format): from the same Download menu. These files need no column mapping.",
    description: "Sample-format help: OFX family",
  },
  uploading: {
    id: "banking.import.uploading",
    defaultMessage: "Reading the file…",
    description: "Status while the file uploads",
  },
  uploadFailed: {
    id: "banking.import.uploadFailed",
    defaultMessage: "The file couldn't be imported: {reason}",
    description: "Error after an upload",
  },
  detectedTable: {
    id: "banking.import.detectedTable",
    defaultMessage:
      "Read as {format} ({encoding}, {delimiter}) — {lines, plural, one {# line} other {# lines}}.",
    description: "Format and encoding detection message of a CSV file",
  },
  detectedXlsx: {
    id: "banking.import.detectedXlsx",
    defaultMessage: "Read as an Excel file — {lines, plural, one {# line} other {# lines}}.",
    description: "Format detection message of an XLSX file",
  },
  detectedOfx: {
    id: "banking.import.detectedOfx",
    defaultMessage:
      "Read as {format} — {lines, plural, one {# line} other {# lines}}. No column mapping needed.",
    description: "Format detection message of an OFX / QFX / QBO file",
  },
  delimiterComma: {
    id: "banking.import.delimiterComma",
    defaultMessage: "comma-separated",
    description: "CSV delimiter",
  },
  delimiterSemicolon: {
    id: "banking.import.delimiterSemicolon",
    defaultMessage: "semicolon-separated",
    description: "CSV delimiter",
  },
  delimiterTab: {
    id: "banking.import.delimiterTab",
    defaultMessage: "tab-separated",
    description: "CSV delimiter",
  },
  delimiterPipe: {
    id: "banking.import.delimiterPipe",
    defaultMessage: "pipe-separated",
    description: "CSV delimiter",
  },
  mappingDetected: {
    id: "banking.import.mappingDetected",
    defaultMessage: "Mapping: {name} (recognised automatically).",
    description: "The saved mapping the auto-detection chose",
  },
  mappingNone: {
    id: "banking.import.mappingNone",
    defaultMessage: "No saved mapping fits this file. Check the columns below.",
    description: "Auto-detection found nothing: the columns were guessed",
  },
  dateAmbiguous: {
    id: "banking.import.dateAmbiguous",
    defaultMessage:
      "These dates could be read as {formats}. Check the date format before you continue.",
    description: "Warning: ambiguous dates such as 03/04/2026",
  },
  savedMapping: {
    id: "banking.import.savedMapping",
    defaultMessage: "Saved mapping",
    description: "Select: saved mappings",
  },
  customMapping: {
    id: "banking.import.customMapping",
    defaultMessage: "Edited for this account",
    description: "Option shown when the columns were changed by hand",
  },
  dateFormat: {
    id: "banking.import.dateFormat",
    defaultMessage: "Date format",
    description: "Select",
  },
  sign: {
    id: "banking.import.amounts",
    defaultMessage: "Amounts",
    description: "Select: sign convention",
  },
  decimal: {
    id: "banking.import.decimal",
    defaultMessage: "Decimal separator",
    description: "Select",
  },
  decimalDot: {
    id: "banking.import.decimalDot",
    defaultMessage: "Point (1,234.56)",
    description: "Option",
  },
  decimalComma: {
    id: "banking.import.decimalComma",
    defaultMessage: "Comma (1 234,56)",
    description: "Option",
  },
  hasHeader: {
    id: "banking.import.hasHeader",
    defaultMessage: "The first row holds the column names",
    description: "Checkbox: the file has a header row",
  },
  skipRows: {
    id: "banking.import.skipRows",
    defaultMessage: "Rows to skip at the top",
    description: "Number field: title rows before the header",
  },
  grid: {
    id: "banking.import.grid",
    defaultMessage: "First rows of the file",
    description: "Accessible name of the mapping grid",
  },
  columnRole: {
    id: "banking.import.columnRole",
    defaultMessage: "Column {n}",
    description: "Accessible name of the role dropdown of a column",
  },
  mapIncomplete: {
    id: "banking.import.mapIncomplete",
    defaultMessage:
      "Choose the date column and the amount column (or the withdrawal and deposit columns).",
    description: "The mapping can't be used yet",
  },
  toPreview: { id: "banking.import.toPreview", defaultMessage: "Preview", description: "Button" },
  previous: { id: "banking.import.previous", defaultMessage: "Back", description: "Button" },
  next: { id: "banking.import.next", defaultMessage: "Continue", description: "Button" },
  previewFailed: {
    id: "banking.import.previewFailed",
    defaultMessage: "The preview couldn't be made: {reason}",
    description: "Error",
  },
  tabs: { id: "banking.import.tabs", defaultMessage: "Lines by status", description: "Tab list" },
  colRow: { id: "banking.import.colRow", defaultMessage: "Row", description: "Column" },
  colDate: { id: "banking.import.colDate", defaultMessage: "Date", description: "Column" },
  colDescription: {
    id: "banking.import.colDescription",
    defaultMessage: "Description",
    description: "Column",
  },
  colAmount: { id: "banking.import.colAmount", defaultMessage: "Amount", description: "Column" },
  colReason: { id: "banking.import.colReason", defaultMessage: "Why", description: "Column" },
  noLines: {
    id: "banking.import.noLines",
    defaultMessage: "No lines here.",
    description: "Empty tab",
  },
  moreLines: {
    id: "banking.import.moreLines",
    defaultMessage: "Showing the first {shown} of {total} lines.",
    description: "The preview shows a page of lines",
  },
  skipErrors: {
    id: "banking.import.skipErrors",
    defaultMessage: "Skip errors and import valid lines",
    description: "Toggle in the preview",
  },
  closing: {
    id: "banking.import.closing",
    defaultMessage: "The statement's closing balance is {amount} on {date}.",
    description: "Statement balance read from the file",
  },
  confirmNew: {
    id: "banking.import.confirmNew",
    defaultMessage:
      "{count, plural, =0 {No new line} one {# new line} other {# new lines}} will be imported into {account}.",
    description: "Confirm step summary",
  },
  confirmDuplicates: {
    id: "banking.import.confirmDuplicates",
    defaultMessage:
      "{count, plural, =0 {No duplicates.} one {# line is already in the account and won't be imported again.} other {# lines are already in the account and won't be imported again.}}",
    description: "Confirm step: duplicates",
  },
  confirmErrors: {
    id: "banking.import.confirmErrors",
    defaultMessage:
      "{count, plural, =0 {No errors.} one {# line with an error is skipped.} other {# lines with errors are skipped.}}",
    description: "Confirm step: errors skipped",
  },
  confirmBlocked: {
    id: "banking.import.confirmBlocked",
    defaultMessage:
      "Some lines have errors. Go back to fix them, or turn on “Skip errors and import valid lines”.",
    description: "Confirm step: errors and the toggle is off",
  },
  importButton: {
    id: "banking.import.importButton",
    defaultMessage: "Import {count, plural, one {# line} other {# lines}}",
    description: "Button: commit the import",
  },
  importing: {
    id: "banking.import.importing",
    defaultMessage: "Importing…",
    description: "Status",
  },
  done: {
    id: "banking.import.done",
    defaultMessage: "{count, plural, one {# line} other {# lines}} imported from {file}",
    description: "Result toast",
  },
  undo: { id: "banking.import.undo", defaultMessage: "Undo import", description: "Toast action" },
  undoAlt: {
    id: "banking.import.undoAlt",
    defaultMessage: "Undo it from the import history on the account page",
    description: "Screen-reader alternative of the toast's Undo",
  },
  undone: {
    id: "banking.import.undone",
    defaultMessage: "Import undone: its lines were removed",
    description: "Toast after undo",
  },
  undoFailed: {
    id: "banking.import.undoFailed",
    defaultMessage: "The import can't be undone: {reason}",
    description: "Toast after a refused undo",
  },
  background: {
    id: "banking.import.background",
    defaultMessage:
      "The file is being imported in the background. Follow its progress in the job tray; the lines appear on the account page when it's done.",
    description: "Large file: the import runs as a background job",
  },
  commitFailed: {
    id: "banking.import.commitFailed",
    defaultMessage: "The import failed: {reason}",
    description: "Error",
  },
  viewAccount: {
    id: "banking.import.viewAccount",
    defaultMessage: "Go to the account",
    description: "Link after the import",
  },
  toastRegion: {
    id: "banking.import.toastRegion",
    defaultMessage: "Notifications ({hotkey})",
    description: "Name of the toast region; {hotkey} is the keyboard shortcut",
  },
  close: { id: "banking.import.close", defaultMessage: "Close", description: "Toast close button" },
  importStatement: {
    id: "banking.import.importStatement",
    defaultMessage: "Import a statement",
    description: "Button on the bank account page",
  },
});

export const roleLabels: Record<Role, MessageDescriptor> = defineMessages({
  date: { id: "banking.import.role.date", defaultMessage: "Date", description: "Column role" },
  description: {
    id: "banking.import.role.description",
    defaultMessage: "Description",
    description: "Column role",
  },
  payee: { id: "banking.import.role.payee", defaultMessage: "Payee", description: "Column role" },
  reference: {
    id: "banking.import.role.reference",
    defaultMessage: "Reference",
    description: "Column role",
  },
  fitid: {
    id: "banking.import.role.fitid",
    defaultMessage: "Bank transaction ID",
    description: "Column role",
  },
  amount: {
    id: "banking.import.role.amount",
    defaultMessage: "Amount",
    description: "Column role",
  },
  debit: {
    id: "banking.import.role.debit",
    defaultMessage: "Withdrawal (money out)",
    description: "Column role",
  },
  credit: {
    id: "banking.import.role.credit",
    defaultMessage: "Deposit (money in)",
    description: "Column role",
  },
  balance: {
    id: "banking.import.role.balance",
    defaultMessage: "Running balance",
    description: "Column role",
  },
  ignore: {
    id: "banking.import.role.ignore",
    defaultMessage: "Don't import",
    description: "Column role",
  },
});

export const signLabels: Record<Sign, MessageDescriptor> = defineMessages({
  signed: {
    id: "banking.import.sign.signed",
    defaultMessage: "One column, negative = money out",
    description: "Sign convention",
  },
  inverted: {
    id: "banking.import.sign.inverted",
    defaultMessage: "One column, positive = money out (credit cards)",
    description: "Sign convention",
  },
  debit_credit: {
    id: "banking.import.sign.debitCredit",
    defaultMessage: "Separate withdrawal and deposit columns",
    description: "Sign convention",
  },
});

export const statusLabels: Record<LineStatus, MessageDescriptor> = defineMessages({
  new: { id: "banking.import.status.new", defaultMessage: "New", description: "Preview tab" },
  duplicate: {
    id: "banking.import.status.duplicate",
    defaultMessage: "Duplicates",
    description: "Preview tab",
  },
  error: {
    id: "banking.import.status.error",
    defaultMessage: "Errors",
    description: "Preview tab",
  },
});

/** Statement lines and import history on the account page (F-02-T13). */
export const lines = defineMessages({
  title: {
    id: "banking.lines.title",
    defaultMessage: "Statement lines",
    description: "Heading on the bank account page",
  },
  uncodedBadge: {
    id: "banking.lines.uncodedBadge",
    defaultMessage: "Uncoded: {count}",
    description: "Badge: number of statement lines not coded yet",
  },
  filter: {
    id: "banking.lines.filter",
    defaultMessage: "Filter statement lines by status",
    description: "Group of status filter buttons",
  },
  filterItem: {
    id: "banking.lines.filterItem",
    defaultMessage: "{label} ({count})",
    description: "Status filter button with its count",
  },
  all: { id: "banking.lines.all", defaultMessage: "All", description: "Status filter" },
  uncoded: { id: "banking.lines.uncoded", defaultMessage: "Uncoded", description: "Status filter" },
  coded: { id: "banking.lines.coded", defaultMessage: "Coded", description: "Status filter" },
  matched: { id: "banking.lines.matched", defaultMessage: "Matched", description: "Status filter" },
  ignored: { id: "banking.lines.ignored", defaultMessage: "Ignored", description: "Status filter" },
  showingImport: {
    id: "banking.lines.showingImport",
    defaultMessage: "Showing the lines of {file}.",
    description: "The list is filtered to one import",
  },
  allLines: {
    id: "banking.lines.allLines",
    defaultMessage: "Show all lines",
    description: "Button: clear the import filter",
  },
  loading: {
    id: "banking.lines.loading",
    defaultMessage: "Loading statement lines…",
    description: "Status",
  },
  failed: {
    id: "banking.lines.failed",
    defaultMessage: "The statement lines couldn't be loaded. Reload the page to try again.",
    description: "Error",
  },
  empty: {
    id: "banking.lines.empty",
    defaultMessage: "No statement lines yet",
    description: "Empty state title",
  },
  emptyBody: {
    id: "banking.lines.emptyBody",
    defaultMessage:
      "Import a statement to see its lines here. They're not in the books until you code or match them.",
    description: "Empty state text",
  },
  noMatch: {
    id: "banking.lines.noMatch",
    defaultMessage: "No line has this status.",
    description: "Filtered list is empty",
  },
  more: {
    id: "banking.lines.more",
    defaultMessage: "Showing {shown} of {total} lines.",
    description: "The list shows a page of lines",
  },
  colDate: { id: "banking.lines.colDate", defaultMessage: "Date", description: "Column" },
  colDescription: {
    id: "banking.lines.colDescription",
    defaultMessage: "Description",
    description: "Column",
  },
  colReference: {
    id: "banking.lines.colReference",
    defaultMessage: "Reference",
    description: "Column",
  },
  colAmount: { id: "banking.lines.colAmount", defaultMessage: "Amount", description: "Column" },
  colStatus: { id: "banking.lines.colStatus", defaultMessage: "Status", description: "Column" },
  colActions: { id: "banking.lines.colActions", defaultMessage: "Actions", description: "Column" },
  actions: {
    id: "banking.lines.actions",
    defaultMessage: "Actions",
    description: "Row menu button",
  },
  actionsFor: {
    id: "banking.lines.actionsFor",
    defaultMessage: "Actions for {date} {description}",
    description: "Accessible name of a statement line's actions button",
  },
  showImport: {
    id: "banking.lines.showImport",
    defaultMessage: "Show the lines of this import",
    description: "Statement line action",
  },
  historyTitle: {
    id: "banking.lines.historyTitle",
    defaultMessage: "Import history",
    description: "Heading on the bank account page",
  },
  historyEmpty: {
    id: "banking.lines.historyEmpty",
    defaultMessage: "No statement imported yet.",
    description: "Empty import history",
  },
  colFile: { id: "banking.lines.colFile", defaultMessage: "File", description: "Column" },
  colImported: {
    id: "banking.lines.colImported",
    defaultMessage: "Imported",
    description: "Column",
  },
  colNew: { id: "banking.lines.colNew", defaultMessage: "New", description: "Column" },
  colDuplicates: {
    id: "banking.lines.colDuplicates",
    defaultMessage: "Duplicates",
    description: "Column",
  },
  colErrors: { id: "banking.lines.colErrors", defaultMessage: "Errors", description: "Column" },
  undo: { id: "banking.lines.undo", defaultMessage: "Undo", description: "Button: undo an import" },
  undoFile: {
    id: "banking.lines.undoFile",
    defaultMessage: "Undo the import of {file}",
    description: "Accessible name of the Undo button of an import",
  },
  undoBlocked: {
    id: "banking.lines.undoBlocked",
    defaultMessage: "Some lines of this import are coded or matched: undo that first.",
    description: "Why Undo is disabled",
  },
  undone: {
    id: "banking.lines.undone",
    defaultMessage: "{file} undone: its lines were removed.",
    description: "After undo",
  },
  undoRefused: {
    id: "banking.lines.undoRefused",
    defaultMessage: "{file} can't be undone: {reason}",
    description: "Undo refused",
  },
});
