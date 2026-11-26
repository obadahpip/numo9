import { defineMessages } from "@/i18n";

import type { PublicReason } from "./api";

/** The public quote page (D-02-T13), `/q/<token>`. */
export const pm = defineMessages({
  pageTitle: {
    id: "sales.publicQuote.pageTitle",
    defaultMessage: "Quote · Numo9",
    description: "Browser tab title of the public quote page",
  },
  title: {
    id: "sales.publicQuote.title",
    defaultMessage: "Quote {number}",
    description: "Heading",
  },
  titled: {
    id: "sales.publicQuote.titled",
    defaultMessage: "Quote {number}: {title}",
    description: "Heading of a quote with a title",
  },
  forCustomer: {
    id: "sales.publicQuote.forCustomer",
    defaultMessage: "For {customer}, dated {date}",
    description: "Who the quote is for",
  },
  expires: {
    id: "sales.publicQuote.expires",
    defaultMessage: "Valid until the end of {date}",
    description: "Expiry date",
  },
  lines: {
    id: "sales.publicQuote.lines",
    defaultMessage: "What's included",
    description: "Heading",
  },
  quantity: {
    id: "sales.publicQuote.quantity",
    defaultMessage: "{quantity} × {price}",
    description: "Quantity and unit price of a line",
  },
  options: {
    id: "sales.publicQuote.options",
    defaultMessage: "Options you can add",
    description: "Heading of the optional lines",
  },
  chooseOne: {
    id: "sales.publicQuote.chooseOne",
    defaultMessage: "Choose one: {group}",
    description: "Heading of an alternative group",
  },
  lineAmount: {
    id: "sales.publicQuote.lineAmount",
    defaultMessage: "{amount} plus {tax} tax",
    description: "Amount and tax of an option",
  },
  totals: { id: "sales.publicQuote.totals", defaultMessage: "Totals", description: "Region" },
  subtotal: { id: "sales.publicQuote.subtotal", defaultMessage: "Subtotal", description: "Row" },
  discount: { id: "sales.publicQuote.discount", defaultMessage: "Discount", description: "Row" },
  tax: { id: "sales.publicQuote.tax", defaultMessage: "Tax", description: "Row" },
  total: { id: "sales.publicQuote.total", defaultMessage: "Total", description: "Row" },
  deposit: {
    id: "sales.publicQuote.deposit",
    defaultMessage: "Deposit due on acceptance",
    description: "Row",
  },
  pdf: { id: "sales.publicQuote.pdf", defaultMessage: "Download the PDF", description: "Link" },
  acceptHeading: {
    id: "sales.publicQuote.acceptHeading",
    defaultMessage: "Accept the quote",
    description: "Heading",
  },
  name: { id: "sales.publicQuote.name", defaultMessage: "Your full name", description: "Field" },
  nameHint: {
    id: "sales.publicQuote.nameHint",
    defaultMessage: "Typing your name is your signature. Drawing one below is optional.",
    description: "Name hint",
  },
  nameRequired: {
    id: "sales.publicQuote.nameRequired",
    defaultMessage: "Type your name to accept the quote.",
    description: "Error",
  },
  signature: {
    id: "sales.publicQuote.signature",
    defaultMessage: "Signature (optional)",
    description: "Signature pad label",
  },
  signatureHint: {
    id: "sales.publicQuote.signatureHint",
    defaultMessage: "Draw with your finger, a pen or the mouse.",
    description: "Signature pad hint",
  },
  clearSignature: {
    id: "sales.publicQuote.clearSignature",
    defaultMessage: "Clear the signature",
    description: "Button",
  },
  accept: {
    id: "sales.publicQuote.accept",
    defaultMessage: "Accept for {total}",
    description: "Big accept button",
  },
  decline: {
    id: "sales.publicQuote.decline",
    defaultMessage: "Decline the quote",
    description: "Button",
  },
  declineReason: {
    id: "sales.publicQuote.declineReason",
    defaultMessage: "Tell us why (optional)",
    description: "Field",
  },
  confirmDecline: {
    id: "sales.publicQuote.confirmDecline",
    defaultMessage: "Decline",
    description: "Button",
  },
  cancel: { id: "sales.publicQuote.cancel", defaultMessage: "Cancel", description: "Button" },
  failed: {
    id: "sales.publicQuote.failed",
    defaultMessage: "That didn't go through. Try again.",
    description: "Error",
  },
  loadFailed: {
    id: "sales.publicQuote.loadFailed",
    defaultMessage: "The quote couldn't be loaded.",
    description: "Error",
  },
  retry: { id: "sales.publicQuote.retry", defaultMessage: "Try again", description: "Button" },
  missing: {
    id: "sales.publicQuote.missing",
    defaultMessage: "This quote link isn't valid.",
    description: "Heading of an unknown link",
  },
  revoked: {
    id: "sales.publicQuote.revoked",
    defaultMessage: "This quote link was withdrawn.",
    description: "Heading of a revoked link",
  },
  askAgain: {
    id: "sales.publicQuote.askAgain",
    defaultMessage: "Ask the business that sent it for a new link.",
    description: "What to do about a bad link",
  },
  askNew: {
    id: "sales.publicQuote.askNew",
    defaultMessage: "Ask {organisation} for a new quote.",
    description: "What to do about an expired or superseded quote",
  },
});

/** Why the quote can't be accepted now (`reason` of the public payload). */
export const reasonMessages = defineMessages({
  expired: {
    id: "sales.publicQuote.reason.expired",
    defaultMessage: "This quote expired at the end of {date}: it can't be accepted any more.",
    description: "Expired quote",
  },
  superseded: {
    id: "sales.publicQuote.reason.superseded",
    defaultMessage: "This quote was revised: a newer version replaces it.",
    description: "Superseded quote",
  },
  accepted: {
    id: "sales.publicQuote.reason.accepted",
    defaultMessage: "Accepted by {name}. Thank you!",
    description: "Accepted quote",
  },
  declined: {
    id: "sales.publicQuote.reason.declined",
    defaultMessage: "You declined this quote.",
    description: "Declined quote",
  },
  invoiced: {
    id: "sales.publicQuote.reason.invoiced",
    defaultMessage: "This quote was accepted and has been invoiced.",
    description: "Invoiced quote",
  },
  not_sent: {
    id: "sales.publicQuote.reason.notSent",
    defaultMessage: "This quote isn't ready yet.",
    description: "Quote not sent",
  },
} satisfies Record<PublicReason, unknown>);
