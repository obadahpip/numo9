import { defineMessages } from "@/i18n";

import type { QuoteTab } from "./api";
import type { QuoteStatus } from "./status";

/** The quote editor (D-02-T12) and its action bar. */
export const qm = defineMessages({
  newTitle: { id: "sales.quote.newTitle", defaultMessage: "New quote", description: "Heading" },
  title: {
    id: "sales.quote.title",
    defaultMessage: "Quote {number}",
    description: "Heading of a saved quote",
  },
  form: { id: "sales.quote.form", defaultMessage: "Quote details", description: "Form name" },
  lines: { id: "sales.quote.lines", defaultMessage: "Quote lines", description: "Grid name" },
  customer: { id: "sales.quote.customer", defaultMessage: "Customer", description: "Field" },
  chooseCustomer: {
    id: "sales.quote.chooseCustomer",
    defaultMessage: "Choose a customer",
    description: "Customer placeholder",
  },
  date: { id: "sales.quote.date", defaultMessage: "Quote date", description: "Field" },
  expiryDate: { id: "sales.quote.expiryDate", defaultMessage: "Expiry date", description: "Field" },
  expiryHint: {
    id: "sales.quote.expiryHint",
    defaultMessage: "The customer can accept it until the end of this day.",
    description: "Expiry date hint",
  },
  heading: { id: "sales.quote.heading", defaultMessage: "Title", description: "Quote title field" },
  summary: { id: "sales.quote.summary", defaultMessage: "Summary", description: "Field" },
  reference: { id: "sales.quote.reference", defaultMessage: "Reference", description: "Field" },
  taxMode: { id: "sales.quote.taxMode", defaultMessage: "Amounts are", description: "Field" },
  taxExclusive: {
    id: "sales.quote.taxExclusive",
    defaultMessage: "Tax exclusive",
    description: "Tax mode",
  },
  taxInclusive: {
    id: "sales.quote.taxInclusive",
    defaultMessage: "Tax inclusive",
    description: "Tax mode",
  },
  taxNone: { id: "sales.quote.taxNone", defaultMessage: "No tax", description: "Tax mode" },
  deposit: {
    id: "sales.quote.deposit",
    defaultMessage: "Deposit on acceptance",
    description: "Field",
  },
  depositNone: {
    id: "sales.quote.depositNone",
    defaultMessage: "No deposit",
    description: "Option",
  },
  depositAmount: {
    id: "sales.quote.depositAmount",
    defaultMessage: "A fixed amount",
    description: "Option",
  },
  depositPercent: {
    id: "sales.quote.depositPercent",
    defaultMessage: "A percentage of the accepted total",
    description: "Option",
  },
  depositValue: {
    id: "sales.quote.depositValue",
    defaultMessage: "{type, select, percent {Deposit %} other {Deposit amount}}",
    description: "Field",
  },
  depositHint: {
    id: "sales.quote.depositHint",
    defaultMessage:
      "When the customer accepts, a draft deposit invoice for {amount} is created. The final invoice deducts it.",
    description: "Deposit hint with the amount at the current total",
  },
  notes: { id: "sales.quote.notes", defaultMessage: "Notes to the customer", description: "Field" },
  optional: { id: "sales.quote.optional", defaultMessage: "Optional", description: "Column" },
  alternative: {
    id: "sales.quote.alternative",
    defaultMessage: "Alternative group",
    description: "Column",
  },
  alternativeHint: {
    id: "sales.quote.alternativeHint",
    defaultMessage: "None",
    description: "Placeholder of an empty alternative group",
  },
  included: { id: "sales.quote.included", defaultMessage: "Included", description: "Column" },
  optionsHint: {
    id: "sales.quote.optionsHint",
    defaultMessage:
      "Optional lines and alternatives not chosen are left out of the total. The customer can tick optional lines and choose one line of each alternative group.",
    description: "Hint under the lines",
  },
  saveDraft: { id: "sales.quote.saveDraft", defaultMessage: "Save draft", description: "Button" },
  saving: { id: "sales.quote.saving", defaultMessage: "Saving…", description: "Busy button" },
  saved: { id: "sales.quote.saved", defaultMessage: "Draft saved.", description: "Notice" },
  failed: {
    id: "sales.quote.failed",
    defaultMessage: "The quote couldn't be saved. Review the fields shown and try again.",
    description: "Error",
  },
  loadFailed: {
    id: "sales.quote.loadFailed",
    defaultMessage: "The quote couldn't be loaded.",
    description: "Error",
  },
  retry: { id: "sales.quote.retry", defaultMessage: "Try again", description: "Button" },
  readOnly: {
    id: "sales.quote.readOnly",
    defaultMessage: "This quote is {status}: revise it to send a changed version.",
    description: "Read-only note of a quote that isn't a draft",
  },
  readOnlyFinal: {
    id: "sales.quote.readOnlyFinal",
    defaultMessage: "This quote is {status} and stays as it was.",
    description: "Read-only note of an invoiced quote",
  },
  supersededBy: {
    id: "sales.quote.supersededBy",
    defaultMessage: "Superseded by {number}: its link shows the customer the quote was revised.",
    description: "Note on a revised quote",
  },
  revisionOf: {
    id: "sales.quote.revisionOf",
    defaultMessage: "Revision of {number}.",
    description: "Note on a revision",
  },
  depositInvoice: {
    id: "sales.quote.depositInvoice",
    defaultMessage: "Deposit invoice {number} ({total}): {status}",
    description: "Link to the deposit invoice",
  },
  draftNumber: {
    id: "sales.quote.draftNumber",
    defaultMessage: "draft",
    description: "Number of a draft invoice",
  },
  invoiceLink: {
    id: "sales.quote.invoiceLink",
    defaultMessage: "Invoiced: {number}",
    description: "Link to the invoice",
  },
  acceptedBy: {
    id: "sales.quote.acceptedBy",
    defaultMessage:
      "Accepted by {name} on {date}{signed, select, true {, signed} other {}}. PDF fingerprint (SHA-256) {hash}.",
    description: "Acceptance evidence",
  },
  declined: {
    id: "sales.quote.declined",
    defaultMessage: "Declined{reason, select, none {} other {: {reason}}}",
    description: "Decline note",
  },
  linkViews: {
    id: "sales.quote.linkViews",
    defaultMessage:
      "Customer link: viewed {views, plural, =0 {not yet} one {once} other {# times}}",
    description: "Public link views",
  },
  actions: { id: "sales.quote.actions", defaultMessage: "Quote actions", description: "Toolbar" },
  send: { id: "sales.quote.send", defaultMessage: "Email to customer", description: "Button" },
  sent: {
    id: "sales.quote.sent",
    defaultMessage: "Quote emailed with its PDF and link.",
    description: "Notice",
  },
  markSent: { id: "sales.quote.markSent", defaultMessage: "Mark as sent", description: "Button" },
  markedSent: {
    id: "sales.quote.markedSent",
    defaultMessage: "Quote marked as sent: copy its link to share it.",
    description: "Notice",
  },
  copyLink: { id: "sales.quote.copyLink", defaultMessage: "Copy link", description: "Button" },
  linkCopied: {
    id: "sales.quote.linkCopied",
    defaultMessage: "Link copied.",
    description: "Notice",
  },
  revokeLinks: {
    id: "sales.quote.revokeLinks",
    defaultMessage: "Withdraw links",
    description: "Button",
  },
  linksRevoked: {
    id: "sales.quote.linksRevoked",
    defaultMessage: "The quote's links were withdrawn.",
    description: "Notice",
  },
  accept: { id: "sales.quote.accept", defaultMessage: "Mark accepted", description: "Button" },
  accepted: {
    id: "sales.quote.accepted",
    defaultMessage: "Quote marked accepted.",
    description: "Notice",
  },
  decline: { id: "sales.quote.decline", defaultMessage: "Mark declined", description: "Button" },
  declineReason: {
    id: "sales.quote.declineReason",
    defaultMessage: "Reason (optional)",
    description: "Field",
  },
  confirmDecline: {
    id: "sales.quote.confirmDecline",
    defaultMessage: "Mark declined",
    description: "Dialog button",
  },
  convert: {
    id: "sales.quote.convert",
    defaultMessage: "Convert to invoice",
    description: "Button",
  },
  revise: { id: "sales.quote.revise", defaultMessage: "Revise", description: "Button" },
  copy: { id: "sales.quote.copy", defaultMessage: "Copy", description: "Button" },
  pdf: { id: "sales.quote.pdf", defaultMessage: "PDF", description: "Link" },
  delete: { id: "sales.quote.delete", defaultMessage: "Delete draft", description: "Button" },
  cancel: { id: "sales.quote.cancel", defaultMessage: "Cancel", description: "Button" },
});

export const quoteStatusLabels = defineMessages({
  draft: { id: "sales.quote.status.draft", defaultMessage: "Draft", description: "Status" },
  sent: { id: "sales.quote.status.sent", defaultMessage: "Sent", description: "Status" },
  viewed: { id: "sales.quote.status.viewed", defaultMessage: "Viewed", description: "Status" },
  accepted: {
    id: "sales.quote.status.accepted",
    defaultMessage: "Accepted",
    description: "Status",
  },
  declined: {
    id: "sales.quote.status.declined",
    defaultMessage: "Declined",
    description: "Status",
  },
  expired: { id: "sales.quote.status.expired", defaultMessage: "Expired", description: "Status" },
  invoiced: {
    id: "sales.quote.status.invoiced",
    defaultMessage: "Invoiced",
    description: "Status",
  },
} satisfies Record<QuoteStatus, unknown>);

/** The list tabs (D-02-T14): the status words of the same enum; Sent covers sent and viewed. */
export const tabLabels = defineMessages({
  all: { id: "sales.quotes.tab.all", defaultMessage: "All", description: "Tab" },
  draft: { id: "sales.quotes.tab.draft", defaultMessage: "Draft", description: "Tab" },
  sent: { id: "sales.quotes.tab.sent", defaultMessage: "Sent", description: "Tab" },
  accepted: { id: "sales.quotes.tab.accepted", defaultMessage: "Accepted", description: "Tab" },
  declined: { id: "sales.quotes.tab.declined", defaultMessage: "Declined", description: "Tab" },
  expired: { id: "sales.quotes.tab.expired", defaultMessage: "Expired", description: "Tab" },
  invoiced: { id: "sales.quotes.tab.invoiced", defaultMessage: "Invoiced", description: "Tab" },
} satisfies Record<QuoteTab, unknown>);

/** The quotes list (D-02-T14). */
export const listMessages = defineMessages({
  heading: { id: "sales.quotes.heading", defaultMessage: "Quotes", description: "Heading" },
  newQuote: { id: "sales.quotes.newQuote", defaultMessage: "New quote", description: "Button" },
  tabs: { id: "sales.quotes.tabs", defaultMessage: "Quotes by status", description: "Tab list" },
  search: { id: "sales.quotes.search", defaultMessage: "Search quotes", description: "Search" },
  searchHint: {
    id: "sales.quotes.searchHint",
    defaultMessage: "Number, customer, title or amount",
    description: "Search placeholder",
  },
  searchButton: {
    id: "sales.quotes.searchButton",
    defaultMessage: "Search",
    description: "Button",
  },
  number: { id: "sales.quotes.number", defaultMessage: "Number", description: "Column" },
  customer: { id: "sales.quotes.customer", defaultMessage: "Customer", description: "Column" },
  title: { id: "sales.quotes.title", defaultMessage: "Title", description: "Column" },
  date: { id: "sales.quotes.date", defaultMessage: "Date", description: "Column" },
  expiry: { id: "sales.quotes.expiry", defaultMessage: "Expires", description: "Column" },
  status: { id: "sales.quotes.status", defaultMessage: "Status", description: "Column" },
  total: { id: "sales.quotes.total", defaultMessage: "Total", description: "Column" },
  empty: {
    id: "sales.quotes.empty",
    defaultMessage: "No quotes here yet.",
    description: "Empty tab",
  },
  noMatches: {
    id: "sales.quotes.noMatches",
    defaultMessage: "No quotes match your search.",
    description: "Empty search",
  },
  previous: { id: "sales.quotes.previous", defaultMessage: "Previous", description: "Button" },
  next: { id: "sales.quotes.next", defaultMessage: "Next", description: "Button" },
  page: {
    id: "sales.quotes.page",
    defaultMessage: "Page {page} of {pages}",
    description: "Pagination",
  },
  loadFailed: {
    id: "sales.quotes.loadFailed",
    defaultMessage: "Quotes couldn't be loaded.",
    description: "Error",
  },
  retry: { id: "sales.quotes.retry", defaultMessage: "Try again", description: "Button" },
});
