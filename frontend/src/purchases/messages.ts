import { defineMessages, type MessageDescriptor } from "@/i18n";

import type { BillStatus } from "./api";

/** Bill editor (E-02-T11…T14). */
export const m = defineMessages({
  newTitle: { id: "purchases.bill.newTitle", defaultMessage: "New bill", description: "Heading" },
  title: {
    id: "purchases.bill.title",
    defaultMessage: "Bill {number}",
    description: "Heading of a numbered bill",
  },
  draftTitle: {
    id: "purchases.bill.draftTitle",
    defaultMessage: "Draft bill",
    description: "Heading",
  },
  document: {
    id: "purchases.bill.document",
    defaultMessage: "Supplier's invoice",
    description: "Left pane: the attached document",
  },
  documentFrame: {
    id: "purchases.bill.documentFrame",
    defaultMessage: "Preview of {name}",
    description: "Accessible name of the document preview",
  },
  noDocument: {
    id: "purchases.bill.noDocument",
    defaultMessage: "Drop the supplier's invoice here to see it beside the form.",
    description: "Empty document pane",
  },
  attach: { id: "purchases.bill.attach", defaultMessage: "Attach a file", description: "Button" },
  uploading: {
    id: "purchases.bill.uploading",
    defaultMessage: "Uploading {name}…",
    description: "Status",
  },
  uploadFailed: {
    id: "purchases.bill.uploadFailed",
    defaultMessage: "{name} couldn't be uploaded. Try again.",
    description: "Error",
  },
  previewUnavailable: {
    id: "purchases.bill.previewUnavailable",
    defaultMessage: "No preview for this file yet. Open it in a new tab.",
    description: "The document has no preview",
  },
  openFile: { id: "purchases.bill.openFile", defaultMessage: "Open the file", description: "Link" },
  form: { id: "purchases.bill.form", defaultMessage: "Bill details", description: "Form name" },
  supplier: { id: "purchases.bill.supplier", defaultMessage: "Supplier", description: "Field" },
  chooseSupplier: {
    id: "purchases.bill.chooseSupplier",
    defaultMessage: "Choose a supplier",
    description: "Empty option",
  },
  supplierInvoiceNo: {
    id: "purchases.bill.supplierInvoiceNo",
    defaultMessage: "Supplier invoice number",
    description: "Field",
  },
  date: { id: "purchases.bill.date", defaultMessage: "Bill date", description: "Field" },
  dueDate: { id: "purchases.bill.dueDate", defaultMessage: "Due date", description: "Field" },
  dueDateHint: {
    id: "purchases.bill.dueDateHint",
    defaultMessage: "Empty: from the supplier's payment terms.",
    description: "Help under the due date",
  },
  reference: { id: "purchases.bill.reference", defaultMessage: "Reference", description: "Field" },
  department: {
    id: "purchases.bill.department",
    defaultMessage: "Department",
    description: "Field",
  },
  taxMode: { id: "purchases.bill.taxMode", defaultMessage: "Amounts are", description: "Field" },
  taxExclusive: {
    id: "purchases.bill.taxExclusive",
    defaultMessage: "Tax exclusive",
    description: "Option",
  },
  taxInclusive: {
    id: "purchases.bill.taxInclusive",
    defaultMessage: "Tax inclusive",
    description: "Option",
  },
  taxNone: { id: "purchases.bill.taxNone", defaultMessage: "No tax", description: "Option" },
  holdback: { id: "purchases.bill.holdback", defaultMessage: "Holdback", description: "Field" },
  holdbackNone: {
    id: "purchases.bill.holdbackNone",
    defaultMessage: "No holdback",
    description: "Option",
  },
  holdbackAmount: {
    id: "purchases.bill.holdbackAmount",
    defaultMessage: "Amount",
    description: "Option",
  },
  holdbackPercent: {
    id: "purchases.bill.holdbackPercent",
    defaultMessage: "% of the total",
    description: "Option",
  },
  holdbackValue: {
    id: "purchases.bill.holdbackValue",
    defaultMessage: "Holdback value",
    description: "Field",
  },
  holdbackHeld: {
    id: "purchases.bill.holdbackHeld",
    defaultMessage: "Held back: {amount}",
    description: "The holdback amount of the bill",
  },
  notes: { id: "purchases.bill.notes", defaultMessage: "Notes", description: "Field" },
  saveDraft: {
    id: "purchases.bill.saveDraft",
    defaultMessage: "Save draft",
    description: "Button",
  },
  submit: {
    id: "purchases.bill.submit",
    defaultMessage: "Submit for approval",
    description: "Button",
  },
  approve: { id: "purchases.bill.approve", defaultMessage: "Approve", description: "Button" },
  saving: {
    id: "purchases.bill.saving",
    defaultMessage: "Saving…",
    description: "Button while saving",
  },
  saved: { id: "purchases.bill.saved", defaultMessage: "Saved as a draft.", description: "Status" },
  submitted: {
    id: "purchases.bill.submitted",
    defaultMessage: "Submitted: it is waiting for approval.",
    description: "Status",
  },
  approved: {
    id: "purchases.bill.approved",
    defaultMessage: "{number} is approved and awaiting payment.",
    description: "Status",
  },
  failed: {
    id: "purchases.bill.failed",
    defaultMessage: "The bill couldn't be saved. Nothing was posted.",
    description: "Error",
  },
  loadFailed: {
    id: "purchases.bill.loadFailed",
    defaultMessage: "The bill couldn't be loaded",
    description: "Error title",
  },
  retry: { id: "purchases.bill.retry", defaultMessage: "Try again", description: "Button" },
  readOnly: {
    id: "purchases.bill.readOnly",
    defaultMessage: "{status}: a posted bill isn't edited. Void it to correct it.",
    description: "Banner of a bill that can't be edited",
  },
  heldAmountDue: {
    id: "purchases.bill.heldAmountDue",
    defaultMessage: "Amount due {amount}",
    description: "The bill's amount due",
  },
});

export const statusLabels: Record<BillStatus, MessageDescriptor> = defineMessages({
  draft: { id: "purchases.bill.status.draft", defaultMessage: "Draft", description: "Bill status" },
  awaiting_approval: {
    id: "purchases.bill.status.awaitingApproval",
    defaultMessage: "Awaiting approval",
    description: "Bill status",
  },
  awaiting_payment: {
    id: "purchases.bill.status.awaitingPayment",
    defaultMessage: "Awaiting payment",
    description: "Bill status",
  },
  partially_paid: {
    id: "purchases.bill.status.partiallyPaid",
    defaultMessage: "Partially paid",
    description: "Bill status",
  },
  paid: { id: "purchases.bill.status.paid", defaultMessage: "Paid", description: "Bill status" },
  void: { id: "purchases.bill.status.void", defaultMessage: "Void", description: "Bill status" },
});

/** Supplier invoice number check and duplicate warnings (E-02-T12). */
export const checks = defineMessages({
  checking: {
    id: "purchases.bill.checking",
    defaultMessage: "Checking the number…",
    description: "Live check in progress",
  },
  open: {
    id: "purchases.bill.openConflict",
    defaultMessage: "Open it",
    description: "Link to the bill that has the number",
  },
  duplicatesTitle: {
    id: "purchases.bill.duplicatesTitle",
    defaultMessage: "This bill looks like one already entered",
    description: "Duplicate warning panel heading",
  },
  duplicatesBody: {
    id: "purchases.bill.duplicatesBody",
    defaultMessage:
      "Same supplier, an amount within 1 % and a date within 10 days. It is only a warning: check before approving.",
    description: "Duplicate warning panel text",
  },
  openSuspect: {
    id: "purchases.bill.openSuspect",
    defaultMessage: "Open {bill}",
    description: "Link to a look-alike bill",
  },
  suspectLine: {
    id: "purchases.bill.suspectLine",
    defaultMessage: "{date} · {total}",
    description: "A look-alike bill: its date and total",
  },
  draftBill: {
    id: "purchases.bill.draftBill",
    defaultMessage: "the draft bill",
    description: "A bill without a number",
  },
});
