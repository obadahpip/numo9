import { defineMessages } from "@/i18n";

/** Expense claim — the approver's view (E-04-T11). */
export const em = defineMessages({
  title: {
    id: "purchases.expense.title",
    defaultMessage: "Expense claim {number}",
    description: "Heading of a submitted expense claim",
  },
  draftTitle: {
    id: "purchases.expense.draftTitle",
    defaultMessage: "Draft expense claim",
    description: "Heading of an expense claim without a number",
  },
  claimant: {
    id: "purchases.expense.claimant",
    defaultMessage: "Claimed by {name}",
    description: "Who the claim is for",
  },
  submitted: {
    id: "purchases.expense.submitted",
    defaultMessage: "Submitted by {name} on {date}",
    description: "Who submitted and when",
  },
  lines: {
    id: "purchases.expense.lines",
    defaultMessage: "Claim lines",
    description: "Table caption",
  },
  colDate: { id: "purchases.expense.col.date", defaultMessage: "Date", description: "Column" },
  colWhat: {
    id: "purchases.expense.col.what",
    defaultMessage: "Receipt or trip",
    description: "Column: merchant, or from → to",
  },
  colCategory: {
    id: "purchases.expense.col.category",
    defaultMessage: "Category",
    description: "Column: the expense account",
  },
  colTax: {
    id: "purchases.expense.col.tax",
    defaultMessage: "Tax (claimable)",
    description: "Column: tax in the receipt and the part claimable as ITC",
  },
  colAmount: {
    id: "purchases.expense.col.amount",
    defaultMessage: "Amount",
    description: "Column",
  },
  trip: {
    id: "purchases.expense.trip",
    defaultMessage: "{from} → {to}, {km} km",
    description: "A mileage line",
  },
  tiers: {
    id: "purchases.expense.tiers",
    defaultMessage: "{km} km × {rate}",
    description: "One rate tier of a mileage line",
  },
  taxCell: {
    id: "purchases.expense.taxCell",
    defaultMessage: "{tax} ({claimable})",
    description: "Tax of a receipt with the claimable part in brackets",
  },
  noReceipt: {
    id: "purchases.expense.noReceipt",
    defaultMessage: "No receipt attached",
    description: "A receipt line without its image",
  },
  receipt: {
    id: "purchases.expense.receipt",
    defaultMessage: "Receipt: {name}",
    description: "The attached receipt file",
  },
  account: {
    id: "purchases.expense.account",
    defaultMessage: "{code} {name}",
    description: "Category account: code and name",
  },
  total: { id: "purchases.expense.total", defaultMessage: "Total", description: "Claim total" },
  duplicates: {
    id: "purchases.expense.duplicates",
    defaultMessage: "Possible duplicate receipts",
    description: "Warning panel heading",
  },
  approve: { id: "purchases.expense.approve", defaultMessage: "Approve", description: "Button" },
  edit: {
    id: "purchases.expense.edit",
    defaultMessage: "Edit the claim",
    description: "Link to the claim form (a draft or a rejected claim of the person)",
  },
  reject: { id: "purchases.expense.reject", defaultMessage: "Reject", description: "Button" },
  rejectTitle: {
    id: "purchases.expense.rejectTitle",
    defaultMessage: "Reject this claim",
    description: "Dialog title",
  },
  reason: {
    id: "purchases.expense.reason",
    defaultMessage: "Why is it rejected? The claimant sees this.",
    description: "Reject dialog: reason label",
  },
  cancel: { id: "purchases.expense.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "purchases.expense.close", defaultMessage: "Close", description: "Dialog close" },
  approved: {
    id: "purchases.expense.approved",
    defaultMessage: "Claim approved.",
    description: "Status message",
  },
  rejected: {
    id: "purchases.expense.rejected",
    defaultMessage: "Claim rejected: the claimant can correct it and submit it again.",
    description: "Status message",
  },
  rejectedBecause: {
    id: "purchases.expense.rejectedBecause",
    defaultMessage: "Rejected by {name}: {reason}",
    description: "Why a claim was rejected",
  },
  blocked: {
    id: "purchases.expense.blocked",
    defaultMessage:
      "{why, select, self {This is your claim, or you entered or submitted it: someone else approves it.} permission {You can't approve expense claims.} limit {This claim is above your expense-claim approval limit.} other {}}",
    description: "Why the person can't approve the claim",
  },
  failed: {
    id: "purchases.expense.failed",
    defaultMessage: "That didn't work and nothing was changed. Try again in a moment.",
    description: "Generic error",
  },
  loading: {
    id: "purchases.expense.loading",
    defaultMessage: "Loading the claim…",
    description: "Placeholder while the claim loads",
  },
});
