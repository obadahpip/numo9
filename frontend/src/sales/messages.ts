import { defineMessages } from "@/i18n";

/** Invoice email composer (D-03a-T15). */
export const em = defineMessages({
  title: { id: "sales.email.title", defaultMessage: "Email invoice", description: "Heading" },
  to: { id: "sales.email.to", defaultMessage: "To", description: "Recipients field" },
  toHint: {
    id: "sales.email.toHint",
    defaultMessage: "Separate addresses with commas.",
    description: "Recipients field hint",
  },
  invalid: {
    id: "sales.email.invalid",
    defaultMessage: "Review these addresses: {addresses}",
    description: "Recipients field error",
  },
  noRecipient: {
    id: "sales.email.noRecipient",
    defaultMessage: "Add at least one email address.",
    description: "Recipients field error",
  },
  subject: { id: "sales.email.subject", defaultMessage: "Subject", description: "Field" },
  subjectRequired: {
    id: "sales.email.subjectRequired",
    defaultMessage: "Add a subject.",
    description: "Subject field error",
  },
  message: { id: "sales.email.message", defaultMessage: "Message", description: "Field" },
  attachment: {
    id: "sales.email.attachment",
    defaultMessage: "Attached: {file}",
    description: "The PDF attached to the email",
  },
  showPreview: {
    id: "sales.email.showPreview",
    defaultMessage: "Preview PDF",
    description: "Button: show the invoice PDF",
  },
  hidePreview: {
    id: "sales.email.hidePreview",
    defaultMessage: "Hide preview",
    description: "Button: hide the invoice PDF",
  },
  previewTitle: {
    id: "sales.email.previewTitle",
    defaultMessage: "Invoice PDF preview",
    description: "Accessible name of the PDF preview frame",
  },
  previewFailed: {
    id: "sales.email.previewFailed",
    defaultMessage: "The PDF couldn't load.",
    description: "Error: the PDF preview failed",
  },
  send: { id: "sales.email.send", defaultMessage: "Send", description: "Button" },
  sending: { id: "sales.email.sending", defaultMessage: "Sending…", description: "Busy button" },
  sent: {
    id: "sales.email.sent",
    defaultMessage: "Invoice sent to {to}.",
    description: "Confirmation",
  },
  failed: {
    id: "sales.email.failed",
    defaultMessage: "The invoice wasn't sent: {reason}",
    description: "Error",
  },
  notSendable: {
    id: "sales.email.notSendable",
    defaultMessage: "Approve the invoice before you email it.",
    description: "Notice: a draft can't be sent",
  },
  loadFailed: {
    id: "sales.email.loadFailed",
    defaultMessage: "The email couldn't load.",
    description: "Error",
  },
  retry: { id: "sales.email.retry", defaultMessage: "Try again", description: "Retry" },
  history: { id: "sales.email.history", defaultMessage: "Sent before", description: "Heading" },
  historyLine: {
    id: "sales.email.historyLine",
    defaultMessage: "{date} to {to}",
    description: "A send of the invoice: when and to whom",
  },
  viewed: {
    id: "sales.email.viewed",
    defaultMessage: "Viewed {date}",
    description: "Badge: the customer opened the invoice",
  },
  notViewed: {
    id: "sales.email.notViewed",
    defaultMessage: "Not viewed yet",
    description: "Badge: the customer hasn't opened the invoice",
  },
});
