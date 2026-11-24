import { defineMessages } from "@/i18n";

/** Approvals inbox (C-04-T12). */
export const im = defineMessages({
  title: { id: "approvals.title", defaultMessage: "Approvals", description: "Heading" },
  list: { id: "approvals.list", defaultMessage: "Waiting for approval", description: "List name" },
  emptyTitle: {
    id: "approvals.emptyTitle",
    defaultMessage: "Nothing waiting for you",
    description: "Empty state",
  },
  emptyBody: {
    id: "approvals.emptyBody",
    defaultMessage: "Journals sent for approval appear here. You'll get a notification too.",
    description: "Empty state text",
  },
  loadFailed: {
    id: "approvals.loadFailed",
    defaultMessage: "The inbox couldn't load.",
    description: "Error",
  },
  retry: { id: "approvals.retry", defaultMessage: "Try again", description: "Retry" },
  yourLimit: {
    id: "approvals.yourLimit",
    defaultMessage: "Your limit {amount}",
    description: "Limit indicator: the person's approval limit",
  },
  noLimit: {
    id: "approvals.noLimit",
    defaultMessage: "You have no approval limit for journals",
    description: "Limit indicator without a limit",
  },
  countsAndKeys: {
    id: "approvals.countsAndKeys",
    defaultMessage:
      "{total, plural, one {# item} other {# items}}, {mine, plural, =0 {none for you to approve} other {# for you to approve}}. ↑/↓ to move, A to approve, R to send back.",
    description: "Counts of the inbox and its keyboard help",
  },
  accountName: {
    id: "approvals.accountName",
    defaultMessage: "{code} · {name}",
    description: "An account in the preview",
  },
  submittedBy: {
    id: "approvals.submittedBy",
    defaultMessage: "Submitted by {name}",
    description: "Who sent the item for approval",
  },
  youCreated: {
    id: "approvals.youCreated",
    defaultMessage: "You created this",
    description: "The person's own item: someone else approves it",
  },
  overLimit: {
    id: "approvals.overLimit",
    defaultMessage: "Above your limit",
    description: "An item the person may not approve: above their limit",
  },
  approve: { id: "approvals.approve", defaultMessage: "Approve", description: "Button (key A)" },
  reject: { id: "approvals.reject", defaultMessage: "Send back", description: "Button (key R)" },
  open: { id: "approvals.open", defaultMessage: "Open the journal", description: "Link" },
  preview: { id: "approvals.preview", defaultMessage: "Preview", description: "Side panel name" },
  account: { id: "approvals.account", defaultMessage: "Account", description: "Column" },
  debit: { id: "approvals.debit", defaultMessage: "Debit", description: "Column" },
  credit: { id: "approvals.credit", defaultMessage: "Credit", description: "Column" },
  rejectTitle: {
    id: "approvals.rejectTitle",
    defaultMessage: "Send it back?",
    description: "Dialog title",
  },
  reason: {
    id: "approvals.reason",
    defaultMessage: "Reason (at least {min} characters)",
    description: "Field",
  },
  cancel: { id: "approvals.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "approvals.close", defaultMessage: "Close", description: "Dialog close" },
  approved: {
    id: "approvals.approved",
    defaultMessage: "Approved and posted.",
    description: "Status",
  },
  rejected: {
    id: "approvals.rejected",
    defaultMessage: "Sent back to its author.",
    description: "Status",
  },
  failed: {
    id: "approvals.failed",
    defaultMessage: "That didn't work. Try again.",
    description: "Error",
  },
});
