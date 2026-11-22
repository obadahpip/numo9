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
    defaultMessage: "Check your connection and try again. Nothing else on this page is blocked.",
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
