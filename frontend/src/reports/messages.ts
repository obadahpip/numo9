import { defineMessages, type MessageDescriptor } from "@/i18n";

/** Report home (K-01-T12). */
export const home = defineMessages({
  title: { id: "reports.home.title", defaultMessage: "Reports", description: "Page heading" },
  intro: {
    id: "reports.home.intro",
    defaultMessage:
      "One place for every financial, tax and operational report. Star the ones you use most.",
    description: "Text under the reports heading",
  },
  search: {
    id: "reports.home.search",
    defaultMessage: "Search reports",
    description: "Search box label on the report home",
  },
  noMatch: {
    id: "reports.home.noMatch",
    defaultMessage: "No report matches “{query}”.",
    description: "Search found nothing",
  },
  tabs: { id: "reports.home.tabs", defaultMessage: "Report views", description: "Tab list name" },
  standard: { id: "reports.home.standard", defaultMessage: "Standard", description: "Tab" },
  drafts: {
    id: "reports.home.drafts",
    defaultMessage: "Drafts",
    description: "Tab: draft layouts",
  },
  published: {
    id: "reports.home.published",
    defaultMessage: "Published",
    description: "Tab: published (frozen) layouts",
  },
  custom: {
    id: "reports.home.custom",
    defaultMessage: "Custom",
    description: "Tab: saved variants",
  },
  categories: {
    id: "reports.home.categories",
    defaultMessage: "Categories",
    description: "Category filter group name",
  },
  all: {
    id: "reports.home.all",
    defaultMessage: "All",
    description: "Category filter: every report",
  },
  favourites: {
    id: "reports.home.favourites",
    defaultMessage: "Favourites",
    description: "Category filter: starred reports",
  },
  noFavourites: {
    id: "reports.home.noFavourites",
    defaultMessage: "Star a report to keep it here.",
    description: "Favourites filter with no starred report",
  },
  showDescriptions: {
    id: "reports.home.showDescriptions",
    defaultMessage: "Show descriptions",
    description: "Switch: one-line description under each report",
  },
  star: {
    id: "reports.home.star",
    defaultMessage: "Add {name} to favourites",
    description: "Star button (not starred yet)",
  },
  unstar: {
    id: "reports.home.unstar",
    defaultMessage: "Remove {name} from favourites",
    description: "Star button (starred)",
  },
  gated: {
    id: "reports.home.gated",
    defaultMessage: "Part of {product} — not in this organisation's package",
    description: "A report whose product the package lacks (shown, never hidden)",
  },
  noLayouts: {
    id: "reports.home.noLayouts",
    defaultMessage: "No saved layouts here yet. Open a report and use Edit layout to save one.",
    description: "Empty Drafts / Published / Custom tab",
  },
  layoutVersion: {
    id: "reports.home.layoutVersion",
    defaultMessage: "{report} · version {version}",
    description: "A saved layout's report and version",
  },
  loadFailed: {
    id: "reports.home.loadFailed",
    defaultMessage: "Reports couldn't be loaded",
    description: "Error title",
  },
  loadFailedBody: {
    id: "reports.home.loadFailedBody",
    defaultMessage: "Nothing was changed. Try again in a moment.",
    description: "Error body",
  },
  retry: { id: "reports.home.retry", defaultMessage: "Try again", description: "Button" },
});

export const categoryLabels: Record<string, MessageDescriptor> = defineMessages({
  financial: {
    id: "reports.category.financial",
    defaultMessage: "Financial",
    description: "Report category",
  },
  tax: { id: "reports.category.tax", defaultMessage: "Tax", description: "Report category" },
  sales: { id: "reports.category.sales", defaultMessage: "Sales", description: "Report category" },
  purchases: {
    id: "reports.category.purchases",
    defaultMessage: "Purchases",
    description: "Report category",
  },
  banking: {
    id: "reports.category.banking",
    defaultMessage: "Banking",
    description: "Report category",
  },
  payroll: {
    id: "reports.category.payroll",
    defaultMessage: "Payroll",
    description: "Report category",
  },
});

/** Report runner (K-01-T13). */
export const runner = defineMessages({
  back: {
    id: "reports.runner.back",
    defaultMessage: "All reports",
    description: "Link back to the report home",
  },
  parameters: {
    id: "reports.runner.parameters",
    defaultMessage: "Report options",
    description: "Name of the parameter bar",
  },
  range: { id: "reports.runner.range", defaultMessage: "Date range", description: "Select label" },
  from: { id: "reports.runner.from", defaultMessage: "From", description: "Date field" },
  to: { id: "reports.runner.to", defaultMessage: "To", description: "Date field" },
  asOf: { id: "reports.runner.asOf", defaultMessage: "As at", description: "Balance date field" },
  compare: { id: "reports.runner.compare", defaultMessage: "Compare", description: "Select label" },
  periods: {
    id: "reports.runner.periods",
    defaultMessage: "Periods",
    description: "How many comparison periods (1–12)",
  },
  basis: { id: "reports.runner.basis", defaultMessage: "Basis", description: "Select label" },
  book: {
    id: "reports.runner.book",
    defaultMessage: "Book",
    description: "Switch label: accounting or tax book",
  },
  tracking: {
    id: "reports.runner.tracking",
    defaultMessage: "Tracking",
    description: "Tracking filter field (category:option, comma-separated)",
  },
  trackingHint: {
    id: "reports.runner.trackingHint",
    defaultMessage: "For example region:east",
    description: "Placeholder of the tracking filter",
  },
  update: {
    id: "reports.runner.update",
    defaultMessage: "Update",
    description: "Button: run the report",
  },
  compact: { id: "reports.runner.compact", defaultMessage: "Compact view", description: "Switch" },
  running: {
    id: "reports.runner.running",
    defaultMessage: "Running the report…",
    description: "Status",
  },
  failed: {
    id: "reports.runner.failed",
    defaultMessage: "The report couldn't be run",
    description: "Error title",
  },
  failedBody: {
    id: "reports.runner.failedBody",
    defaultMessage: "Nothing was changed. Review the options and try again.",
    description: "Error body",
  },
  retry: { id: "reports.runner.retry", defaultMessage: "Try again", description: "Button" },
  unknown: {
    id: "reports.runner.unknown",
    defaultMessage: "There's no such report",
    description: "Unknown report slug",
  },
  unknownBody: {
    id: "reports.runner.unknownBody",
    defaultMessage: "The address may be old. Every report is listed on the report home.",
    description: "Unknown report slug: what to do",
  },
  gatedBody: {
    id: "reports.runner.gatedBody",
    defaultMessage: "Your data is kept. The organisation owner can add it to the package.",
    description: "402 from the run: what stays and who can fix it",
  },
  gated: {
    id: "reports.runner.gated",
    defaultMessage: "{name} is part of {product}, which isn't in this organisation's package.",
    description: "402 from the run",
  },
  drill: {
    id: "reports.runner.drill",
    defaultMessage: "Show the lines of {row}, {column}",
    description: "Drill button on a report figure",
  },
  noActivity: {
    id: "reports.runner.noActivity",
    defaultMessage: "No activity in this period",
    description: "Hint of a report with no postings in its period (never a dash)",
  },
  noActivityCell: {
    id: "reports.runner.noActivityCell",
    defaultMessage: "No activity",
    description: "An empty cell of a report",
  },
  showZeroRows: {
    id: "reports.runner.showZeroRows",
    defaultMessage: "Show zero rows",
    description: "Switch: show accounts with no activity",
  },
  runFinancialYear: {
    id: "reports.runner.runFinancialYear",
    defaultMessage: "Run this financial year",
    description: "Action under the no-activity hint",
  },
  note: {
    id: "reports.runner.note",
    defaultMessage: "Note:",
    description: "Read before a cell note",
  },
  export: {
    id: "reports.runner.export",
    defaultMessage: "Export",
    description: "Export menu button",
  },
  editLayout: {
    id: "reports.runner.editLayout",
    defaultMessage: "Edit layout",
    description: "Opens the layout editor panel",
  },
  layoutName: {
    id: "reports.runner.layoutName",
    defaultMessage: "Layout: {name} (version {version})",
    description: "The layout a run uses",
  },
  publishedLayout: {
    id: "reports.runner.publishedLayout",
    defaultMessage: "Published — this is the stored snapshot; later postings don't change it.",
    description: "A published layout's run",
  },
});

export const presetLabels: Record<string, MessageDescriptor> = defineMessages({
  this_month: {
    id: "reports.preset.thisMonth",
    defaultMessage: "This month",
    description: "Date range preset",
  },
  last_month: {
    id: "reports.preset.lastMonth",
    defaultMessage: "Last month",
    description: "Date range preset",
  },
  this_quarter: {
    id: "reports.preset.thisQuarter",
    defaultMessage: "This quarter",
    description: "Date range preset",
  },
  last_quarter: {
    id: "reports.preset.lastQuarter",
    defaultMessage: "Last quarter",
    description: "Date range preset",
  },
  this_financial_year: {
    id: "reports.preset.thisFinancialYear",
    defaultMessage: "This financial year",
    description: "Date range preset",
  },
  last_financial_year: {
    id: "reports.preset.lastFinancialYear",
    defaultMessage: "Last financial year",
    description: "Date range preset",
  },
  month_to_date: {
    id: "reports.preset.monthToDate",
    defaultMessage: "Month to date",
    description: "Date range preset",
  },
  quarter_to_date: {
    id: "reports.preset.quarterToDate",
    defaultMessage: "Quarter to date",
    description: "Date range preset",
  },
  year_to_date: {
    id: "reports.preset.yearToDate",
    defaultMessage: "Year to date",
    description: "Date range preset",
  },
  custom: {
    id: "reports.preset.custom",
    defaultMessage: "Custom dates",
    description: "Date range preset",
  },
});

export const compareLabels: Record<string, MessageDescriptor> = defineMessages({
  none: {
    id: "reports.compare.none",
    defaultMessage: "No comparison",
    description: "Compare option",
  },
  previous: {
    id: "reports.compare.previous",
    defaultMessage: "Previous periods",
    description: "Compare option",
  },
  prior_year: {
    id: "reports.compare.priorYear",
    defaultMessage: "Prior year",
    description: "Compare option",
  },
});

export const basisLabels: Record<string, MessageDescriptor> = defineMessages({
  default: {
    id: "reports.basis.default",
    defaultMessage: "Organisation default",
    description: "Basis option: the tax-settings basis",
  },
  accrual: { id: "reports.basis.accrual", defaultMessage: "Accrual", description: "Basis option" },
  cash: { id: "reports.basis.cash", defaultMessage: "Cash", description: "Basis option" },
});

export const bookLabels: Record<string, MessageDescriptor> = defineMessages({
  accounting: {
    id: "reports.book.accounting",
    defaultMessage: "Accounting",
    description: "Book option",
  },
  tax: { id: "reports.book.tax", defaultMessage: "Tax", description: "Book option" },
});

export const exportLabels: Record<string, MessageDescriptor> = defineMessages({
  pdf: { id: "reports.export.pdf", defaultMessage: "PDF (Letter)", description: "Export format" },
  xlsx: {
    id: "reports.export.xlsx",
    defaultMessage: "Excel / Google Sheets (formulas for totals)",
    description: "Export format",
  },
  csv: { id: "reports.export.csv", defaultMessage: "CSV", description: "Export format" },
});

/** Drill-down drawer (K-01-T14). */
export const drillMessages = defineMessages({
  summary: {
    id: "reports.drill.summary",
    defaultMessage: "{count, plural, one {# line} other {# lines}} · total {total}",
    description: "Drawer header: line count and total (= the figure)",
  },
  period: {
    id: "reports.drill.period",
    defaultMessage: "{from} to {to}",
    description: "Drawer header: the figure's period",
  },
  upTo: {
    id: "reports.drill.upTo",
    defaultMessage: "Up to {to}",
    description: "Drawer header: a balance figure (from the start of the books)",
  },
  lines: { id: "reports.drill.lines", defaultMessage: "Lines", description: "Table name" },
  date: { id: "reports.drill.date", defaultMessage: "Date", description: "Column" },
  source: { id: "reports.drill.source", defaultMessage: "Source", description: "Column" },
  description: {
    id: "reports.drill.description",
    defaultMessage: "Description",
    description: "Column",
  },
  amount: { id: "reports.drill.amount", defaultMessage: "Amount", description: "Column" },
  openInvoice: {
    id: "reports.drill.openInvoice",
    defaultMessage: "Open invoice",
    description: "Link to the line's source document: an invoice",
  },
  openBankTransaction: {
    id: "reports.drill.openBankTransaction",
    defaultMessage: "Open bank transaction",
    description: "Link to the line's source document: a bank transaction",
  },
  openDocument: {
    id: "reports.drill.openDocument",
    defaultMessage: "Open document",
    description: "Link to the line's source document (another kind)",
  },
  openJournal: {
    id: "reports.drill.openJournal",
    defaultMessage: "Open journal",
    description: "Link to the journal entry (no other source document)",
  },
  journalNumber: {
    id: "reports.drill.journalNumber",
    defaultMessage: "Journal {number}",
    description: "The line's journal number under the source link",
  },
  previous: {
    id: "reports.drill.previous",
    defaultMessage: "Previous page",
    description: "Button",
  },
  next: { id: "reports.drill.next", defaultMessage: "Next page", description: "Button" },
  page: {
    id: "reports.drill.page",
    defaultMessage: "Page {page} of {pages}",
    description: "Pagination status",
  },
  exportLines: {
    id: "reports.drill.exportLines",
    defaultMessage: "Export lines (CSV)",
    description: "Download the drawer's lines",
  },
  close: { id: "reports.drill.close", defaultMessage: "Close", description: "Close the drawer" },
  loading: {
    id: "reports.drill.loading",
    defaultMessage: "Loading the lines…",
    description: "Status",
  },
  failed: {
    id: "reports.drill.failed",
    defaultMessage: "The lines couldn't be loaded",
    description: "Error title",
  },
  retry: { id: "reports.drill.retry", defaultMessage: "Try again", description: "Button" },
});

/** Layout editor panel (K-01-T15). */
export const layoutMessages = defineMessages({
  title: {
    id: "reports.layout.title",
    defaultMessage: "Edit layout",
    description: "Panel heading",
  },
  name: { id: "reports.layout.name", defaultMessage: "Layout name", description: "Field" },
  defaultName: {
    id: "reports.layout.defaultName",
    defaultMessage: "{report} layout",
    description: "Default name of a new layout",
  },
  rows: { id: "reports.layout.rows", defaultMessage: "Rows", description: "List heading" },
  rowsHint: {
    id: "reports.layout.rowsHint",
    defaultMessage: "Drag rows, or use the arrows, to reorder them.",
    description: "Help under the rows heading",
  },
  rename: {
    id: "reports.layout.rename",
    defaultMessage: "Label for {row}",
    description: "Rename field of a row (the chart keeps the account name)",
  },
  hide: { id: "reports.layout.hide", defaultMessage: "Hide {row}", description: "Checkbox" },
  moveUp: { id: "reports.layout.moveUp", defaultMessage: "Move {row} up", description: "Button" },
  moveDown: {
    id: "reports.layout.moveDown",
    defaultMessage: "Move {row} down",
    description: "Button",
  },
  drag: { id: "reports.layout.drag", defaultMessage: "Drag {row}", description: "Drag handle" },
  textBlocks: {
    id: "reports.layout.textBlocks",
    defaultMessage: "Text blocks",
    description: "Heading",
  },
  addText: {
    id: "reports.layout.addText",
    defaultMessage: "Add text after {row}",
    description: "Button: a text block after the row",
  },
  addTextTop: {
    id: "reports.layout.addTextTop",
    defaultMessage: "Add text at the top",
    description: "Button: a text block before every row",
  },
  textAfter: {
    id: "reports.layout.textAfter",
    defaultMessage: "Text after {row}",
    description: "Text block field",
  },
  textTop: {
    id: "reports.layout.textTop",
    defaultMessage: "Text at the top",
    description: "Text block field",
  },
  removeText: {
    id: "reports.layout.removeText",
    defaultMessage: "Remove this text",
    description: "Button",
  },
  footnotes: { id: "reports.layout.footnotes", defaultMessage: "Footnotes", description: "Field" },
  noteHeading: {
    id: "reports.layout.noteHeading",
    defaultMessage: "Note on a cell",
    description: "Heading",
  },
  noteRow: { id: "reports.layout.noteRow", defaultMessage: "Row", description: "Select label" },
  noteColumn: {
    id: "reports.layout.noteColumn",
    defaultMessage: "Column",
    description: "Select label",
  },
  noteWholeRow: {
    id: "reports.layout.noteWholeRow",
    defaultMessage: "The whole row",
    description: "Column option: a note on the row",
  },
  noteText: { id: "reports.layout.noteText", defaultMessage: "Note", description: "Field" },
  saveNote: { id: "reports.layout.saveNote", defaultMessage: "Save note", description: "Button" },
  noteSaved: {
    id: "reports.layout.noteSaved",
    defaultMessage: "Note saved. It stays when the report is run again.",
    description: "Status",
  },
  saveDraft: {
    id: "reports.layout.saveDraft",
    defaultMessage: "Save as draft",
    description: "Button",
  },
  publish: { id: "reports.layout.publish", defaultMessage: "Publish", description: "Button" },
  saveCustom: {
    id: "reports.layout.saveCustom",
    defaultMessage: "Save as custom",
    description: "Button",
  },
  publishHint: {
    id: "reports.layout.publishHint",
    defaultMessage: "Publishing stores this run as it is: later postings never change it.",
    description: "Help next to Publish",
  },
  published: {
    id: "reports.layout.published",
    defaultMessage:
      "Version {version} is published and can't be changed. Saving starts version {next}.",
    description: "Editing a published layout",
  },
  saved: { id: "reports.layout.saved", defaultMessage: "Saved as a draft.", description: "Status" },
  savedCustom: {
    id: "reports.layout.savedCustom",
    defaultMessage: "Saved as a custom layout.",
    description: "Status",
  },
  publishedNow: {
    id: "reports.layout.publishedNow",
    defaultMessage: "Published version {version}.",
    description: "Status",
  },
  failed: {
    id: "reports.layout.failed",
    defaultMessage: "The layout couldn't be saved: {detail}",
    description: "Error",
  },
  close: {
    id: "reports.layout.close",
    defaultMessage: "Close the layout editor",
    description: "Button",
  },
});
