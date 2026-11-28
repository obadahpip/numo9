import { defineMessages, type MessageDescriptor } from "@/i18n";

import type { BankAccountType } from "./api";

export const m = defineMessages({
  title: { id: "banking.title", defaultMessage: "Banking", description: "Page heading (F-01)" },
  intro: {
    id: "banking.intro",
    defaultMessage:
      "Bank, credit card and cash accounts work the moment you add them — no feed, import or reconciliation needed.",
    description: "Text under the banking heading",
  },
  addAccount: {
    id: "banking.addAccount",
    defaultMessage: "Add account",
    description: "Button: open the add-account side-sheet",
  },
  spendMoney: { id: "banking.spendMoney", defaultMessage: "Spend money", description: "Button" },
  receiveMoney: {
    id: "banking.receiveMoney",
    defaultMessage: "Receive money",
    description: "Button",
  },
  ledgerBalance: {
    id: "banking.ledgerBalance",
    defaultMessage: "Balance in Numo9",
    description: "Card label: the ledger balance of the account",
  },
  owed: {
    id: "banking.owed",
    defaultMessage: "{amount} owed",
    description: "Ledger balance of a credit card, line of credit or loan (a credit balance)",
  },
  statementBalance: {
    id: "banking.statementBalance",
    defaultMessage: "Statement balance {amount} on {date}",
    description: "Optional statement balance entered by the user, with its date",
  },
  noStatement: {
    id: "banking.noStatement",
    defaultMessage: "No statement balance entered",
    description: "Card line when no statement balance was entered",
  },
  reconcileOptional: {
    id: "banking.reconcileOptional",
    defaultMessage: "Not reconciled — optional",
    description: "Chip: reconciliation is optional and never blocks anything (gap-27)",
  },
  reconcileTracked: {
    id: "banking.reconcileTracked",
    defaultMessage: "Reconciliation tracked",
    description: "Chip: the organisation chose to reconcile this account",
  },
  lastActivity: {
    id: "banking.lastActivity",
    defaultMessage: "Last activity {date}",
    description: "Card line: date of the latest transaction",
  },
  noActivity: {
    id: "banking.noActivity",
    defaultMessage: "No transactions yet",
    description: "Card line: the account has no transaction",
  },
  emptyTitle: {
    id: "banking.emptyTitle",
    defaultMessage: "No bank account yet",
    description: "Empty state title",
  },
  emptyBody: {
    id: "banking.emptyBody",
    defaultMessage:
      "Add a chequing, savings, credit card or cash account and record spend and receive money right away. No bank feed is needed, and nothing else is blocked meanwhile.",
    description: "Empty state body",
  },
  loading: {
    id: "banking.loading",
    defaultMessage: "Loading bank accounts…",
    description: "Screen-reader text while balances load",
  },
  loadFailed: {
    id: "banking.loadFailed",
    defaultMessage: "Bank accounts couldn't be loaded",
    description: "Error state title",
  },
  loadFailedBody: {
    id: "banking.loadFailedBody",
    defaultMessage: "Verify your connection and try again. Nothing else on this page is blocked.",
    description: "Error state body",
  },
  retry: { id: "banking.retry", defaultMessage: "Try again", description: "Retry button" },
  archivedHeading: {
    id: "banking.archivedHeading",
    defaultMessage: "Archived ({count})",
    description: "Heading of the archived accounts section, with how many there are",
  },
  showArchived: {
    id: "banking.showArchived",
    defaultMessage: "Show archived accounts",
    description: "Toggle: show the archived accounts section",
  },
  archivedNote: {
    id: "banking.archivedNote",
    defaultMessage: "Hidden from pickers, kept in reports.",
    description: "Text under the archived heading",
  },
  restore: { id: "banking.restore", defaultMessage: "Restore", description: "Button" },
  restored: {
    id: "banking.restored",
    defaultMessage: "{name} is back in your accounts.",
    description: "Status after restoring an archived account",
  },
});

export const typeLabels: Record<BankAccountType, MessageDescriptor> = defineMessages({
  chequing: { id: "banking.type.chequing", defaultMessage: "Chequing", description: "Type" },
  savings: { id: "banking.type.savings", defaultMessage: "Savings", description: "Type" },
  credit_card: {
    id: "banking.type.creditCard",
    defaultMessage: "Credit card",
    description: "Type",
  },
  line_of_credit: {
    id: "banking.type.lineOfCredit",
    defaultMessage: "Line of credit",
    description: "Type",
  },
  loan: { id: "banking.type.loan", defaultMessage: "Loan", description: "Type" },
  cash: { id: "banking.type.cash", defaultMessage: "Cash / petty cash", description: "Type" },
  clearing: { id: "banking.type.clearing", defaultMessage: "Clearing", description: "Type" },
});

export const sheet = defineMessages({
  title: {
    id: "banking.add.title",
    defaultMessage: "Add a bank account",
    description: "Title of the add-account side-sheet (F-01-T09)",
  },
  description: {
    id: "banking.add.description",
    defaultMessage: "It's ready to use as soon as you add it. You can rename it later.",
    description: "Text under the side-sheet title",
  },
  close: { id: "banking.add.close", defaultMessage: "Close", description: "Close button" },
  type: { id: "banking.add.type", defaultMessage: "Type", description: "Field label" },
  name: { id: "banking.add.name", defaultMessage: "Name", description: "Field label" },
  namePlaceholder: {
    id: "banking.add.namePlaceholder",
    defaultMessage: "e.g. TD Business Chequing",
    description: "Placeholder of the name field",
  },
  nameRequired: {
    id: "banking.add.nameRequired",
    defaultMessage: "Give the account a name.",
    description: "Validation message",
  },
  institution: {
    id: "banking.add.institution",
    defaultMessage: "Institution",
    description: "Field label: the bank",
  },
  institutionHint: {
    id: "banking.add.institutionHint",
    defaultMessage: "Pick a Canadian bank or type any name.",
    description: "Hint under the institution field",
  },
  currency: { id: "banking.add.currency", defaultMessage: "Currency", description: "Field label" },
  currencyHint: {
    id: "banking.add.currencyHint",
    defaultMessage: "Fixed once the account has transactions.",
    description: "Hint under the currency field",
  },
  last4: {
    id: "banking.add.last4",
    defaultMessage: "Last 4 digits (optional)",
    description: "Field label: last digits of the account number",
  },
  last4Hint: {
    id: "banking.add.last4Hint",
    defaultMessage: "Stored encrypted and shown masked.",
    description: "Hint under the last-4-digits field",
  },
  last4Invalid: {
    id: "banking.add.last4Invalid",
    defaultMessage: "Enter exactly 4 digits.",
    description: "Validation message",
  },
  submit: { id: "banking.add.submit", defaultMessage: "Add account", description: "Button" },
  cancel: { id: "banking.add.cancel", defaultMessage: "Cancel", description: "Button" },
  saving: { id: "banking.add.saving", defaultMessage: "Adding…", description: "Busy button" },
  failed: {
    id: "banking.add.failed",
    defaultMessage: "The account couldn't be added. Try again.",
    description: "Generic error",
  },
  ready: {
    id: "banking.add.ready",
    defaultMessage: "{name} is ready.",
    description: "Success notice after adding an account",
  },
  recordTransaction: {
    id: "banking.add.recordTransaction",
    defaultMessage: "Record a transaction",
    description: "Next action in the success notice: open spend money for the new account",
  },
  dismiss: { id: "banking.add.dismiss", defaultMessage: "Dismiss", description: "Button" },
});

export const typeHelp: Record<BankAccountType, MessageDescriptor> = defineMessages({
  chequing: {
    id: "banking.help.chequing",
    defaultMessage: "Money you keep at the bank and pay from: a current asset.",
    description: "Plain-language help of the type",
  },
  savings: {
    id: "banking.help.savings",
    defaultMessage: "Money set aside at the bank: a current asset.",
    description: "Plain-language help of the type",
  },
  credit_card: {
    id: "banking.help.creditCard",
    defaultMessage:
      "What you owe on a business card: a current liability. Paying it from chequing is a transfer.",
    description: "Plain-language help of the type",
  },
  line_of_credit: {
    id: "banking.help.lineOfCredit",
    defaultMessage: "Money borrowed as needed from the bank: a current liability.",
    description: "Plain-language help of the type",
  },
  loan: {
    id: "banking.help.loan",
    defaultMessage: "A loan you repay over more than a year: a long-term liability.",
    description: "Plain-language help of the type",
  },
  cash: {
    id: "banking.help.cash",
    defaultMessage: "Notes and coins on hand, such as petty cash: a current asset.",
    description: "Plain-language help of the type",
  },
  clearing: {
    id: "banking.help.clearing",
    defaultMessage:
      "Money in transit, such as card-processor payouts not yet deposited: a current asset.",
    description: "Plain-language help of the type",
  },
});

export const reg = defineMessages({
  back: { id: "banking.detail.back", defaultMessage: "Banking", description: "Breadcrumb link" },
  statementNone: {
    id: "banking.detail.statementNone",
    defaultMessage: "Statement balance: not entered",
    description: "Account header when no statement balance was entered",
  },
  grid: {
    id: "banking.detail.grid",
    defaultMessage: "Transactions",
    description: "Accessible name of the transactions grid",
  },
  results: {
    id: "banking.detail.results",
    defaultMessage: "{shown} of {total} transactions",
    description: "Live region after filtering",
  },
  loading: {
    id: "banking.detail.loading",
    defaultMessage: "Loading transactions…",
    description: "Loading text",
  },
  colDate: { id: "banking.detail.colDate", defaultMessage: "Date", description: "Column" },
  colJournal: { id: "banking.detail.colJournal", defaultMessage: "Journal", description: "Column" },
  colContact: { id: "banking.detail.colContact", defaultMessage: "Contact", description: "Column" },
  colDescription: {
    id: "banking.detail.colDescription",
    defaultMessage: "Description",
    description: "Column",
  },
  colReference: {
    id: "banking.detail.colReference",
    defaultMessage: "Reference",
    description: "Column",
  },
  colReceived: {
    id: "banking.detail.colReceived",
    defaultMessage: "Received",
    description: "Column: money in",
  },
  colSpent: {
    id: "banking.detail.colSpent",
    defaultMessage: "Spent",
    description: "Column: money out",
  },
  colBalance: {
    id: "banking.detail.colBalance",
    defaultMessage: "Running balance",
    description: "Column: the account balance after the row",
  },
  colStatus: { id: "banking.detail.colStatus", defaultMessage: "Status", description: "Column" },
  statusPosted: {
    id: "banking.detail.statusPosted",
    defaultMessage: "Posted",
    description: "Row status",
  },
  statusReversed: {
    id: "banking.detail.statusReversed",
    defaultMessage: "Reversed",
    description: "Row status",
  },
  statusVoided: {
    id: "banking.detail.statusVoided",
    defaultMessage: "Voided",
    description: "Row status: a voided spend / receive money",
  },
  filters: {
    id: "banking.detail.filters",
    defaultMessage: "Filter transactions",
    description: "Accessible name of the filter group",
  },
  from: { id: "banking.detail.from", defaultMessage: "From", description: "Filter: start date" },
  to: { id: "banking.detail.to", defaultMessage: "To", description: "Filter: end date" },
  contact: {
    id: "banking.detail.contact",
    defaultMessage: "Contact",
    description: "Filter: contact",
  },
  anyContact: {
    id: "banking.detail.anyContact",
    defaultMessage: "Any contact",
    description: "Contact filter: no filter",
  },
  amountMin: {
    id: "banking.detail.amountMin",
    defaultMessage: "Amount from",
    description: "Filter: smallest amount",
  },
  amountMax: {
    id: "banking.detail.amountMax",
    defaultMessage: "Amount to",
    description: "Filter: largest amount",
  },
  status: { id: "banking.detail.status", defaultMessage: "Status", description: "Filter" },
  anyStatus: {
    id: "banking.detail.anyStatus",
    defaultMessage: "Any status",
    description: "Status filter: no filter",
  },
  apply: { id: "banking.detail.apply", defaultMessage: "Apply", description: "Button" },
  clear: { id: "banking.detail.clear", defaultMessage: "Clear", description: "Button" },
  exportCsv: {
    id: "banking.detail.exportCsv",
    defaultMessage: "Export CSV",
    description: "Download the filtered transactions as CSV",
  },
  exportXlsx: {
    id: "banking.detail.exportXlsx",
    defaultMessage: "Export Excel",
    description: "Download the filtered transactions as XLSX",
  },
  empty: {
    id: "banking.detail.empty",
    defaultMessage: "No transactions yet",
    description: "Empty state title",
  },
  emptyBody: {
    id: "banking.detail.emptyBody",
    defaultMessage: "Spend money or receive money to see it here, with the running balance.",
    description: "Empty state body",
  },
  noMatch: {
    id: "banking.detail.noMatch",
    defaultMessage: "No transaction matches these filters.",
    description: "No results state",
  },
  loadFailed: {
    id: "banking.detail.loadFailed",
    defaultMessage: "This account couldn't be loaded",
    description: "Error title",
  },
});

export const prompt = defineMessages({
  title: {
    id: "banking.prompt.title",
    defaultMessage: "Add your first bank account",
    description: "No-bank-account prompt title (F-01-T12)",
  },
  body: {
    id: "banking.prompt.body",
    defaultMessage:
      "Record spend and receive money right away — no feed or plan upgrade needed. Nothing is blocked meanwhile.",
    description: "No-bank-account prompt text",
  },
  add: { id: "banking.prompt.add", defaultMessage: "Add account", description: "Prompt button" },
  dismiss: {
    id: "banking.prompt.dismiss",
    defaultMessage: "Hide for 7 days",
    description: "Prompt dismiss button: hides it for this person for 7 days",
  },
});

/** Spend money / Receive money form (F-01-T10). */
export const money = defineMessages({
  spendTitle: {
    id: "banking.money.spendTitle",
    defaultMessage: "Spend money",
    description: "Heading of the spend money form",
  },
  receiveTitle: {
    id: "banking.money.receiveTitle",
    defaultMessage: "Receive money",
    description: "Heading of the receive money form",
  },
  bankAccount: {
    id: "banking.money.bankAccount",
    defaultMessage: "Bank account",
    description: "Field: the bank, card or cash account the money leaves or arrives in",
  },
  date: { id: "banking.money.date", defaultMessage: "Date", description: "Field" },
  paidTo: {
    id: "banking.money.paidTo",
    defaultMessage: "Paid to",
    description: "Field of spend money: the supplier (contact) paid",
  },
  receivedFrom: {
    id: "banking.money.receivedFrom",
    defaultMessage: "Received from",
    description: "Field of receive money: the customer (contact) who paid",
  },
  noContact: {
    id: "banking.money.noContact",
    defaultMessage: "No contact",
    description: "Empty choice of the contact field (optional)",
  },
  chooseContact: {
    id: "banking.money.chooseContact",
    defaultMessage: "Choose a contact",
    description: "Empty choice of the contact field when a contact is required",
  },
  contactRequired: {
    id: "banking.money.contactRequired",
    defaultMessage: "A line's account needs a contact.",
    description: "Under the contact field when a line's account requires a contact",
  },
  reference: {
    id: "banking.money.reference",
    defaultMessage: "Reference",
    description: "Field: receipt number, cheque number…",
  },
  taxMode: {
    id: "banking.money.taxMode",
    defaultMessage: "Amounts are",
    description: "Field: whether line amounts include tax",
  },
  taxExclusive: {
    id: "banking.money.taxExclusive",
    defaultMessage: "Tax exclusive",
    description: "Tax mode option",
  },
  taxInclusive: {
    id: "banking.money.taxInclusive",
    defaultMessage: "Tax inclusive",
    description: "Tax mode option",
  },
  taxNone: {
    id: "banking.money.taxNone",
    defaultMessage: "No tax",
    description: "Tax mode option",
  },
  attachments: {
    id: "banking.money.attachments",
    defaultMessage: "Supporting documents",
    description: "Heading of the attachment drop zone",
  },
  attachHint: {
    id: "banking.money.attachHint",
    defaultMessage: "Drop a receipt here, or choose a file.",
    description: "Text in the attachment drop zone",
  },
  attachButton: {
    id: "banking.money.attachButton",
    defaultMessage: "Attach a document",
    description: "File picker of the drop zone",
  },
  attachmentRequired: {
    id: "banking.money.attachmentRequired",
    defaultMessage: "A line's account needs a supporting document.",
    description: "Drop zone message when an attachment is required",
  },
  uploading: {
    id: "banking.money.uploading",
    defaultMessage: "Uploading {name}…",
    description: "While a document uploads",
  },
  uploadFailed: {
    id: "banking.money.uploadFailed",
    defaultMessage: "{name} couldn't be uploaded. Try again.",
    description: "A document upload failed",
  },
  saveSpend: {
    id: "banking.money.saveSpend",
    defaultMessage: "Record spend",
    description: "Button: posts the spend money transaction",
  },
  saveReceive: {
    id: "banking.money.saveReceive",
    defaultMessage: "Record receipt",
    description: "Button: posts the receive money transaction",
  },
  saving: { id: "banking.money.saving", defaultMessage: "Saving…", description: "Button busy" },
  failed: {
    id: "banking.money.failed",
    defaultMessage: "The transaction couldn't be saved. Try again.",
    description: "Unexpected error",
  },
  loadFailed: {
    id: "banking.money.loadFailed",
    defaultMessage: "The form couldn't load.",
    description: "Error state",
  },
  retry: { id: "banking.money.retry", defaultMessage: "Try again", description: "Retry button" },
});
