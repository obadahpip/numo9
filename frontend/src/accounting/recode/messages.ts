import { defineMessages } from "@/i18n";

/** Find & recode with undo (C-07-T10 – T13). */
export const rm = defineMessages({
  title: { id: "recode.title", defaultMessage: "Find and recode", description: "Page heading" },
  intro: {
    id: "recode.intro",
    defaultMessage:
      "Find posted lines by any mix of conditions, then change their account, tax code, tracking or contact in one go. Amounts never change: each entry is reversed and posted again with the new coding, and the whole recode can be undone while its periods are open.",
    description: "Text under the heading",
  },
  // ---- condition builder (T10)
  conditions: {
    id: "recode.conditions",
    defaultMessage: "Conditions",
    description: "Heading of the conditions pane",
  },
  match: {
    id: "recode.match",
    defaultMessage: "Find lines matching",
    description: "Label of the All / Any choice",
  },
  matchOption: {
    id: "recode.matchOption",
    defaultMessage: "{match, select, any {any condition} other {all conditions}}",
    description: "All / Any option",
  },
  field: { id: "recode.field", defaultMessage: "Field", description: "Condition field label" },
  fieldName: {
    id: "recode.fieldName",
    defaultMessage:
      "{field, select, type {Type} status {Status} account {Account} bank_account {Bank account} date {Date} amount {Amount} tax_code {Tax code} entered_by {Entered by} contact {Contact} number {Journal number} reference {Reference} tracking {Tracking} book {Book} other {Field}}",
    description: "Name of a condition field",
  },
  op: { id: "recode.op", defaultMessage: "Operator", description: "Condition operator label" },
  opName: {
    id: "recode.opName",
    defaultMessage:
      "{op, select, is {is} not {is not} in {is one of} on {on} before {before} after {after} between {between} eq {equals} gt {more than} gte {at least} lt {less than} lte {at most} contains {contains} empty {is empty} other {is}}",
    description: "Name of a condition operator",
  },
  value: { id: "recode.value", defaultMessage: "Value", description: "Condition value label" },
  valueTo: {
    id: "recode.valueTo",
    defaultMessage: "and",
    description: "Label of a range's second value (between X and Y)",
  },
  category: {
    id: "recode.category",
    defaultMessage: "Category",
    description: "Tracking category input",
  },
  option: { id: "recode.option", defaultMessage: "Option", description: "Tracking option input" },
  inHint: {
    id: "recode.inHint",
    defaultMessage: "Separate values with commas",
    description: "Hint of an 'is one of' value",
  },
  choice: {
    id: "recode.choice",
    defaultMessage:
      "{value, select, manual {Manual journal} sales {Sales} purchase {Purchases} payment {Payment} payroll {Payroll} opening {Opening balance} adjustment {Adjustment} bank {Bank transaction} posted {Posted} reversed {Reversed} both {Both books} accounting {Accounting book} tax {Tax book} other {{value}}}",
    description: "A fixed value of a condition (entry type, status, book)",
  },
  chooseAccount: {
    id: "recode.chooseAccount",
    defaultMessage: "Choose an account",
    description: "Account select placeholder",
  },
  addCondition: {
    id: "recode.addCondition",
    defaultMessage: "Add condition",
    description: "Button",
  },
  removeCondition: {
    id: "recode.removeCondition",
    defaultMessage: "Remove condition {position}",
    description: "Icon button removing a condition row",
  },
  conditionRow: {
    id: "recode.conditionRow",
    defaultMessage: "Condition {position}",
    description: "Accessible name of a condition row",
  },
  incomplete: {
    id: "recode.incomplete",
    defaultMessage: "Give a value to every condition, or remove it.",
    description: "Shown when a condition has no value",
  },
  search: { id: "recode.search", defaultMessage: "Find lines", description: "Button" },
  // ---- results grid (T11)
  results: { id: "recode.results", defaultMessage: "Lines found", description: "Tab" },
  excludedTab: {
    id: "recode.excludedTab",
    defaultMessage: "Excluded",
    description: "Tab of the lines that can't be recoded",
  },
  summary: {
    id: "recode.summary",
    defaultMessage:
      "{lines, plural, one {# line} other {# lines}} · {accounts, plural, one {# account} other {# accounts}} · {excluded, plural, =0 {nothing excluded} one {# excluded} other {# excluded}}",
    description: "Sticky summary of the search",
  },
  selected: {
    id: "recode.selected",
    defaultMessage: "{selected, plural, one {# line selected} other {# lines selected}}",
    description: "How many lines are chosen",
  },
  selectPage: {
    id: "recode.selectPage",
    defaultMessage: "Select the lines on this page",
    description: "Header checkbox",
  },
  selectAll: {
    id: "recode.selectAll",
    defaultMessage: "Select all {count} lines",
    description: "Button selecting every line across pages",
  },
  clearSelection: {
    id: "recode.clearSelection",
    defaultMessage: "Clear selection",
    description: "Button",
  },
  selectLine: {
    id: "recode.selectLine",
    defaultMessage: "Select {number} line {line}",
    description: "Row checkbox",
  },
  colJournal: { id: "recode.colJournal", defaultMessage: "Journal", description: "Column" },
  journalLine: {
    id: "recode.journalLine",
    defaultMessage: "{number} · line {line}",
    description: "A journal line in the grids",
  },
  colDate: { id: "recode.colDate", defaultMessage: "Date", description: "Column" },
  colAccount: { id: "recode.colAccount", defaultMessage: "Account", description: "Column" },
  colDescription: {
    id: "recode.colDescription",
    defaultMessage: "Description",
    description: "Column",
  },
  colDebit: { id: "recode.colDebit", defaultMessage: "Debit", description: "Column" },
  colCredit: { id: "recode.colCredit", defaultMessage: "Credit", description: "Column" },
  colTax: { id: "recode.colTax", defaultMessage: "Tax code", description: "Column" },
  colContact: { id: "recode.colContact", defaultMessage: "Contact", description: "Column" },
  colTracking: { id: "recode.colTracking", defaultMessage: "Tracking", description: "Column" },
  colReason: {
    id: "recode.colReason",
    defaultMessage: "Why it can't be recoded",
    description: "Column of the excluded tab",
  },
  page: {
    id: "recode.page",
    defaultMessage: "Page {page} of {pages}",
    description: "Pager position",
  },
  previous: { id: "recode.previous", defaultMessage: "Previous", description: "Pager button" },
  next: { id: "recode.next", defaultMessage: "Next", description: "Pager button" },
  noLines: {
    id: "recode.noLines",
    defaultMessage: "No posted line matches these conditions.",
    description: "Empty results",
  },
  noExcluded: {
    id: "recode.noExcluded",
    defaultMessage: "Every line found can be recoded.",
    description: "Empty excluded tab",
  },
  // ---- new coding, preview, confirm (T12)
  newCoding: {
    id: "recode.newCoding",
    defaultMessage: "New coding",
    description: "Heading of the changes form",
  },
  newCodingHint: {
    id: "recode.newCodingHint",
    defaultMessage: "Leave a field empty to keep it as it is.",
    description: "Hint under the changes heading",
  },
  newAccount: {
    id: "recode.newAccount",
    defaultMessage: "New account",
    description: "Changes field",
  },
  keepAccount: {
    id: "recode.keepAccount",
    defaultMessage: "Keep the account",
    description: "Option: no account change",
  },
  newTaxCode: {
    id: "recode.newTaxCode",
    defaultMessage: "New tax code",
    description: "Changes field",
  },
  clearTax: {
    id: "recode.clearTax",
    defaultMessage: "Remove the tax code",
    description: "Checkbox",
  },
  newTracking: {
    id: "recode.newTracking",
    defaultMessage: "New tracking",
    description: "Changes field group",
  },
  newContact: {
    id: "recode.newContact",
    defaultMessage: "New contact (its ID)",
    description: "Changes field",
  },
  clearContact: {
    id: "recode.clearContact",
    defaultMessage: "Remove the contact",
    description: "Checkbox",
  },
  noChanges: {
    id: "recode.noChanges",
    defaultMessage: "Choose at least one new value.",
    description: "Shown when no change is chosen",
  },
  previewButton: {
    id: "recode.previewButton",
    defaultMessage: "Preview the recode",
    description: "Button",
  },
  preview: { id: "recode.preview", defaultMessage: "Preview", description: "Heading" },
  previewSummary: {
    id: "recode.previewSummary",
    defaultMessage:
      "{lines, plural, one {# line changes} other {# lines change}} · {unchanged, plural, =0 {} one {# already coded this way ·} other {# already coded this way ·}} {totals, select, yes {totals unchanged} other {totals would change}}",
    description: "Preview summary line",
  },
  before: { id: "recode.before", defaultMessage: "Before", description: "Diff column" },
  after: { id: "recode.after", defaultMessage: "After", description: "Diff column" },
  changedField: {
    id: "recode.changedField",
    defaultMessage: "{field}: {before} changes to {after}",
    description: "Screen-reader text of a changed value in the preview diff",
  },
  none: { id: "recode.none", defaultMessage: "None", description: "An empty coding value" },
  taxImpact: {
    id: "recode.taxImpact",
    defaultMessage:
      "Tax: changing the tax code changes the tax these lines carry by {delta}. The amounts already posted stay as they are; confirm the tax change to go on.",
    description: "Tax impact warning",
  },
  booksTotals: {
    id: "recode.booksTotals",
    defaultMessage: "{book}: debits {debit} · credits {credit}",
    description: "Totals of a book in the preview",
  },
  bookName: {
    id: "recode.bookName",
    defaultMessage: "{book, select, tax {Tax book} other {Accounting book}}",
    description: "Name of a book",
  },
  batchName: {
    id: "recode.batchName",
    defaultMessage: "Name of this recode (optional)",
    description: "Input label",
  },
  recode: {
    id: "recode.recode",
    defaultMessage: "Recode {count, plural, one {# line} other {# lines}}",
    description: "Button opening the confirm dialog",
  },
  confirmTitle: {
    id: "recode.confirmTitle",
    defaultMessage: "Recode {count, plural, one {# line} other {# lines}}?",
    description: "Confirm dialog title",
  },
  confirmBody: {
    id: "recode.confirmBody",
    defaultMessage:
      "{entries, plural, one {# entry is} other {# entries are}} reversed and posted again on {entries, plural, one {its} other {their}} own dates with the new coding. Debits {debit} and credits {credit} stay the same. {excluded, plural, =0 {} one {# excluded line is left as it is.} other {# excluded lines are left as they are.}}",
    description: "Confirm dialog consequences",
  },
  confirmTax: {
    id: "recode.confirmTax",
    defaultMessage: "I understand the tax these lines carry changes by {delta}",
    description: "Checkbox in the confirm dialog",
  },
  confirm: { id: "recode.confirm", defaultMessage: "Recode", description: "Confirm button" },
  cancel: { id: "recode.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "recode.close", defaultMessage: "Close", description: "Dialog close label" },
  running: {
    id: "recode.running",
    defaultMessage: "Recoding {done} of {total} lines…",
    description: "Progress toast of a background recode",
  },
  done: {
    id: "recode.done",
    defaultMessage:
      "{lines, plural, one {# line recoded} other {# lines recoded}}{problems, plural, =0 {} one {, # not recoded} other {, # not recoded}}",
    description: "Toast when a recode finishes",
  },
  failed: {
    id: "recode.failed",
    defaultMessage: "That didn't work. Try again.",
    description: "Generic error",
  },
  loading: { id: "recode.loading", defaultMessage: "Loading…", description: "Loading" },
  // ---- batch history (T13)
  history: { id: "recode.history", defaultMessage: "Recode history", description: "Heading" },
  noHistory: {
    id: "recode.noHistory",
    defaultMessage: "No recode yet.",
    description: "Empty history",
  },
  colBatch: { id: "recode.colBatch", defaultMessage: "Recode", description: "Column" },
  colRun: { id: "recode.colRun", defaultMessage: "Run by", description: "Column" },
  colLines: { id: "recode.colLines", defaultMessage: "Lines", description: "Column" },
  colActions: { id: "recode.colActions", defaultMessage: "Actions", description: "Column" },
  colStatus: { id: "recode.colStatus", defaultMessage: "Status", description: "Column" },
  status: {
    id: "recode.status",
    defaultMessage:
      "{status, select, draft {Draft} running {Running} completed {Completed} failed {Failed} undone {Undone} other {{status}}}",
    description: "Batch status",
  },
  runBy: {
    id: "recode.runBy",
    defaultMessage: "{name} · {when}",
    description: "Who ran a recode and when",
  },
  report: {
    id: "recode.report",
    defaultMessage: "Report ({format})",
    description: "Download link of the audit report",
  },
  undo: { id: "recode.undo", defaultMessage: "Undo", description: "Button" },
  undoTitle: {
    id: "recode.undoTitle",
    defaultMessage: "Undo “{name}”?",
    description: "Undo dialog title",
  },
  undoBody: {
    id: "recode.undoBody",
    defaultMessage:
      "Every line goes back to its coding before this recode: the re-posted entries are reversed and posted again, latest first.",
    description: "Undo dialog consequences",
  },
  undoReason: {
    id: "recode.undoReason",
    defaultMessage: "Reason (optional)",
    description: "Undo reason input",
  },
  undoBlocked: {
    id: "recode.undoBlocked",
    defaultMessage: "Undo isn't available: {reasons}",
    description: "Why Undo is disabled",
  },
  undoNotYet: {
    id: "recode.undoNotYet",
    defaultMessage: "Undo is available once the recode has run.",
    description: "Why Undo is disabled for a running recode",
  },
  undone: {
    id: "recode.undone",
    defaultMessage: "Recode undone.",
    description: "Toast after undo",
  },
  problemsTitle: {
    id: "recode.problemsTitle",
    defaultMessage: "Not recoded",
    description: "Heading of a batch's problems",
  },
});
