import { defineMessages } from "@/i18n";

/** Contact tabs: Activity (B-02-T10), Statements (T11), Reconciliation (T12). */
export const tm = defineMessages({
  tabs: { id: "contacts.tabs.label", defaultMessage: "Contact sections", description: "Tab list" },
  details: { id: "contacts.tabs.details", defaultMessage: "Details", description: "Tab" },
  activity: { id: "contacts.tabs.activity", defaultMessage: "Activity", description: "Tab" },
  statements: { id: "contacts.tabs.statements", defaultMessage: "Statements", description: "Tab" },
  reconciliation: {
    id: "contacts.tabs.reconciliation",
    defaultMessage: "Supplier statements",
    description: "Tab",
  },
  filter: { id: "contacts.activity.filter", defaultMessage: "Show", description: "Filter" },
  allTypes: {
    id: "contacts.activity.allTypes",
    defaultMessage: "Everything",
    description: "Filter",
  },
  noActivity: {
    id: "contacts.activity.none",
    defaultMessage: "Nothing has happened with this contact yet.",
    description: "Empty",
  },
  eventLine: {
    id: "contacts.activity.line",
    defaultMessage: "{when} · {title}",
    description: "A timeline entry",
  },
  by: { id: "contacts.activity.by", defaultMessage: "by {name}", description: "Who" },
  noteLabel: {
    id: "contacts.activity.noteLabel",
    defaultMessage: "Add a note",
    description: "Field",
  },
  addNote: { id: "contacts.activity.addNote", defaultMessage: "Save note", description: "Button" },
  kind: { id: "contacts.statement.kind", defaultMessage: "Statement", description: "Field" },
  outstanding: {
    id: "contacts.statement.outstanding",
    defaultMessage: "Outstanding (open items)",
    description: "Option",
  },
  activityKind: {
    id: "contacts.statement.activity",
    defaultMessage: "Activity (a date range)",
    description: "Option",
  },
  asAt: { id: "contacts.statement.asAt", defaultMessage: "As at", description: "Field" },
  from: { id: "contacts.statement.from", defaultMessage: "From", description: "Field" },
  preview: { id: "contacts.statement.preview", defaultMessage: "Preview", description: "Button" },
  pdf: { id: "contacts.statement.pdf", defaultMessage: "Open the PDF", description: "Link" },
  send: {
    id: "contacts.statement.send",
    defaultMessage: "Email the statement",
    description: "Button",
  },
  sent: {
    id: "contacts.statement.sent",
    defaultMessage: "Statement sent to {to}.",
    description: "After sending",
  },
  colDate: { id: "contacts.statement.colDate", defaultMessage: "Date", description: "Column" },
  colDocument: {
    id: "contacts.statement.colDocument",
    defaultMessage: "Document",
    description: "Column",
  },
  colDue: { id: "contacts.statement.colDue", defaultMessage: "Due", description: "Column" },
  colAmount: {
    id: "contacts.statement.colAmount",
    defaultMessage: "Amount",
    description: "Column",
  },
  colBalance: {
    id: "contacts.statement.colBalance",
    defaultMessage: "Balance",
    description: "Column",
  },
  opening: {
    id: "contacts.statement.opening",
    defaultMessage: "Opening balance {amount}",
    description: "Activity statement",
  },
  amountDue: {
    id: "contacts.statement.amountDue",
    defaultMessage: "Amount due {amount}",
    description: "Statement total",
  },
  history: {
    id: "contacts.statement.history",
    defaultMessage: "Sent before",
    description: "Heading",
  },
  historyLine: {
    id: "contacts.statement.historyLine",
    defaultMessage: "{date}: as at {as_at}, {amount} to {to}",
    description: "A sent statement",
  },
  failed: {
    id: "contacts.tabs.failed",
    defaultMessage: "We couldn't do that: {reason}",
    description: "Error",
  },
  statementChoice: {
    id: "contacts.recon.statement",
    defaultMessage: "Their statement",
    description: "Select",
  },
  noStatements: {
    id: "contacts.recon.none",
    defaultMessage:
      "No supplier statement yet. Add one from the supplier's file to compare it with your bills.",
    description: "Empty",
  },
  theirs: {
    id: "contacts.recon.theirs",
    defaultMessage: "Their statement",
    description: "Column heading",
  },
  ours: {
    id: "contacts.recon.ours",
    defaultMessage: "Our bills and payments",
    description: "Column heading",
  },
  totals: {
    id: "contacts.recon.totals",
    defaultMessage: "They say {theirs}, we have {ours}: difference {difference}.",
    description: "Summary",
  },
  column: {
    id: "contacts.recon.column",
    defaultMessage: "{side} — not matched",
    description: "Column heading: side of the reconciliation, unmatched lines",
  },
  matched: { id: "contacts.recon.matched", defaultMessage: "Matched", description: "Heading" },
  how: {
    id: "contacts.recon.how",
    defaultMessage:
      "{how, select, number {by number} amount_date {by amount and date} other {by hand}}",
    description: "How a pair matched",
  },
  pairLine: {
    id: "contacts.recon.pairLine",
    defaultMessage:
      "{theirs} ↔ {ours} ({how}){difference, select, none {} other {, difference {difference}}}",
    description: "A matched pair",
  },
  lineText: {
    id: "contacts.recon.lineText",
    defaultMessage: "{date} · {document} · {amount}",
    description: "One side's line",
  },
  matchTo: {
    id: "contacts.recon.matchTo",
    defaultMessage: "Match {line} to",
    description: "Select name",
  },
  choose: { id: "contacts.recon.choose", defaultMessage: "Choose…", description: "Empty option" },
  note: { id: "contacts.recon.note", defaultMessage: "Note on {line}", description: "Field" },
  saveNote: { id: "contacts.recon.saveNote", defaultMessage: "Save note", description: "Button" },
});
