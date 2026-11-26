import { defineMessages } from "@/i18n";

import type { InvoiceStatus } from "./api";

/** The invoice editor (D-03a-T13), its action bar, posting preview and period ribbon (T14). */
export const im = defineMessages({
  newTitle: { id: "sales.invoice.newTitle", defaultMessage: "New invoice", description: "Heading" },
  draftTitle: {
    id: "sales.invoice.draftTitle",
    defaultMessage: "Draft invoice",
    description: "Heading of a saved draft (no number yet)",
  },
  title: {
    id: "sales.invoice.title",
    defaultMessage: "Invoice {number}",
    description: "Heading of a numbered invoice",
  },
  form: { id: "sales.invoice.form", defaultMessage: "Invoice details", description: "Form name" },
  customer: { id: "sales.invoice.customer", defaultMessage: "Customer", description: "Field" },
  chooseCustomer: {
    id: "sales.invoice.chooseCustomer",
    defaultMessage: "Choose a customer",
    description: "Customer placeholder",
  },
  date: { id: "sales.invoice.date", defaultMessage: "Invoice date", description: "Field" },
  dueDate: { id: "sales.invoice.dueDate", defaultMessage: "Due date", description: "Field" },
  dueDateHint: {
    id: "sales.invoice.dueDateHint",
    defaultMessage: "Leave empty to use the customer's payment terms.",
    description: "Due date hint",
  },
  reference: { id: "sales.invoice.reference", defaultMessage: "Reference", description: "Field" },
  taxMode: {
    id: "sales.invoice.taxMode",
    defaultMessage: "Amounts are",
    description: "Tax mode field",
  },
  taxExclusive: {
    id: "sales.invoice.taxExclusive",
    defaultMessage: "Tax exclusive",
    description: "Tax mode",
  },
  taxInclusive: {
    id: "sales.invoice.taxInclusive",
    defaultMessage: "Tax inclusive",
    description: "Tax mode",
  },
  taxNone: { id: "sales.invoice.taxNone", defaultMessage: "No tax", description: "Tax mode" },
  notes: {
    id: "sales.invoice.notes",
    defaultMessage: "Notes to the customer",
    description: "Field",
  },
  attachments: {
    id: "sales.invoice.attachments",
    defaultMessage: "Attachments",
    description: "Heading of the attachments",
  },
  attach: { id: "sales.invoice.attach", defaultMessage: "Attach a file", description: "Button" },
  noAttachments: {
    id: "sales.invoice.noAttachments",
    defaultMessage: "No files attached.",
    description: "Empty attachments",
  },
  uploading: {
    id: "sales.invoice.uploading",
    defaultMessage: "Uploading {name}…",
    description: "Upload in progress",
  },
  uploadFailed: {
    id: "sales.invoice.uploadFailed",
    defaultMessage: "{name} couldn't be uploaded. Try again.",
    description: "Upload error",
  },
  amountDue: {
    id: "sales.invoice.amountDue",
    defaultMessage: "Amount due {amount}",
    description: "Amount due on a posted invoice",
  },
  readOnly: {
    id: "sales.invoice.readOnly",
    defaultMessage:
      "This invoice is {status}: it can't be edited. Void it or copy it to correct it.",
    description: "Note on a posted invoice",
  },
  saveDraft: { id: "sales.invoice.saveDraft", defaultMessage: "Save draft", description: "Button" },
  saving: { id: "sales.invoice.saving", defaultMessage: "Saving…", description: "Busy button" },
  saved: { id: "sales.invoice.saved", defaultMessage: "Draft saved.", description: "Notice" },
  failed: {
    id: "sales.invoice.failed",
    defaultMessage: "The invoice couldn't be saved. Review the fields marked and try again.",
    description: "Save error",
  },
  loadFailed: {
    id: "sales.invoice.loadFailed",
    defaultMessage: "The invoice couldn't be loaded.",
    description: "Error state",
  },
  retry: { id: "sales.invoice.retry", defaultMessage: "Try again", description: "Retry button" },
  // ---- action bar (T14)
  actions: {
    id: "sales.invoice.actions",
    defaultMessage: "Invoice actions",
    description: "Accessible name of the action bar",
  },
  approve: { id: "sales.invoice.approve", defaultMessage: "Approve", description: "Button" },
  approveHint: {
    id: "sales.invoice.approveHint",
    defaultMessage: "Approving gives the invoice its number and posts it.",
    description: "Hint next to Approve",
  },
  submitForApproval: {
    id: "sales.invoice.submitForApproval",
    defaultMessage: "Submit for approval",
    description: "Approve when the approval rule applies",
  },
  approved: {
    id: "sales.invoice.approved",
    defaultMessage: "Invoice {number} approved and posted.",
    description: "Notice",
  },
  submitted: {
    id: "sales.invoice.submitted",
    defaultMessage: "Sent for approval.",
    description: "Notice",
  },
  approveWaiting: {
    id: "sales.invoice.approveWaiting",
    defaultMessage: "Approve and post",
    description: "Approve an invoice awaiting approval",
  },
  email: { id: "sales.invoice.email", defaultMessage: "Email", description: "Button" },
  pdf: { id: "sales.invoice.pdf", defaultMessage: "PDF", description: "Download the PDF" },
  copy: { id: "sales.invoice.copy", defaultMessage: "Copy", description: "Copy to a new invoice" },
  copyToQuote: {
    id: "sales.invoice.copyToQuote",
    defaultMessage: "Copy to quote",
    description: "Copy to a new quote",
  },
  void: { id: "sales.invoice.void", defaultMessage: "Void", description: "Button" },
  voidTitle: {
    id: "sales.invoice.voidTitle",
    defaultMessage: "Void invoice {number}?",
    description: "Void dialog heading",
  },
  voidIntro: {
    id: "sales.invoice.voidIntro",
    defaultMessage:
      "Its journal is reversed on the void date and it keeps its number. This can't be undone.",
    description: "Void dialog text",
  },
  voidDate: { id: "sales.invoice.voidDate", defaultMessage: "Void date", description: "Field" },
  voidReason: { id: "sales.invoice.voidReason", defaultMessage: "Reason", description: "Field" },
  voided: { id: "sales.invoice.voided", defaultMessage: "Invoice voided.", description: "Notice" },
  delete: { id: "sales.invoice.delete", defaultMessage: "Delete draft", description: "Button" },
  cancel: { id: "sales.invoice.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "sales.invoice.close", defaultMessage: "Close", description: "Button" },
  previewPosting: {
    id: "sales.invoice.previewPosting",
    defaultMessage: "Preview posting",
    description: "Opens the posting preview drawer",
  },
  postingTitle: {
    id: "sales.invoice.postingTitle",
    defaultMessage: "{posted, select, true {Posted journal} other {What approval posts}}",
    description: "Posting preview drawer heading",
  },
  postingIntro: {
    id: "sales.invoice.postingIntro",
    defaultMessage:
      "Accounts receivable is debited; each revenue account and each tax control account is credited separately.",
    description: "Posting preview text",
  },
  postingIncomplete: {
    id: "sales.invoice.postingIncomplete",
    defaultMessage: "Every line with an amount needs an account before the invoice can post.",
    description: "Posting preview of an incomplete invoice",
  },
  account: { id: "sales.invoice.account", defaultMessage: "Account", description: "Column" },
  debit: { id: "sales.invoice.debit", defaultMessage: "Debit", description: "Column" },
  credit: { id: "sales.invoice.credit", defaultMessage: "Credit", description: "Column" },
  totalRow: { id: "sales.invoice.totalRow", defaultMessage: "Total", description: "Total row" },
  accountName: {
    id: "sales.invoice.accountName",
    defaultMessage: "{code} · {name}",
    description: "Account in the posting preview",
  },
  // ---- period ribbon (T14)
  ribbon: {
    id: "sales.invoice.ribbon",
    defaultMessage: "Period",
    description: "Accessible name of the period ribbon",
  },
  ribbonOpen: {
    id: "sales.invoice.ribbonOpen",
    defaultMessage: "Open period",
    description: "Ribbon: the date can post",
  },
  ribbonLocked: {
    id: "sales.invoice.ribbonLocked",
    defaultMessage: "Locked: on or before the sales lock date {date}",
    description: "Ribbon: the AR lock stops the date",
  },
  ribbonLock: {
    id: "sales.invoice.ribbonLock",
    defaultMessage: "Sales lock date {date}",
    description: "Ribbon: the AR lock date",
  },
  ribbonTax: {
    id: "sales.invoice.ribbonTax",
    defaultMessage: "GST/HST period {start} – {end}",
    description: "Ribbon: the filing period of the date",
  },
  ribbonTaxFiled: {
    id: "sales.invoice.ribbonTaxFiled",
    defaultMessage: "GST/HST period {start} – {end} is filed",
    description: "Ribbon: the filing period is filed",
  },
});

export const statusLabels = defineMessages({
  draft: { id: "sales.invoice.status.draft", defaultMessage: "Draft", description: "Status" },
  awaiting_approval: {
    id: "sales.invoice.status.awaiting_approval",
    defaultMessage: "Awaiting approval",
    description: "Status",
  },
  approved: {
    id: "sales.invoice.status.approved",
    defaultMessage: "Approved",
    description: "Status",
  },
  sent: { id: "sales.invoice.status.sent", defaultMessage: "Sent", description: "Status" },
  partially_paid: {
    id: "sales.invoice.status.partially_paid",
    defaultMessage: "Partially paid",
    description: "Status",
  },
  paid: { id: "sales.invoice.status.paid", defaultMessage: "Paid", description: "Status" },
  void: { id: "sales.invoice.status.void", defaultMessage: "Void", description: "Status" },
} satisfies Record<InvoiceStatus, unknown>);
