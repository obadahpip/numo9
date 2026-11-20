import { defineMessages } from "@/i18n";

export const m = defineMessages({
  crumb: {
    id: "console.founding.crumb",
    defaultMessage: "Platform console · Founding offer",
    description: "Breadcrumb of the console's founding offer screen",
  },
  title: {
    id: "console.founding.title",
    defaultMessage: "Founding offer",
    description: "Heading of the console's founding offer screen (U-08)",
  },
  intro: {
    id: "console.founding.intro",
    defaultMessage:
      "The first {cap, number} organisations to pay get every product, whatever their package. Each place is given once; a released number is never given again.",
    description: "Text under the heading",
  },
  counter: {
    id: "console.founding.counter",
    defaultMessage: "{allocated, number} of {cap, number} places given",
    description: "Founding counter, e.g. 427 of 1,000 places given",
  },
  summary: {
    id: "console.founding.summary",
    defaultMessage: "{remaining, number} left · {active, number} founding organisations now",
    description: "Places still available, and slots not released",
  },
  noPayment: {
    id: "console.founding.noPayment",
    defaultMessage: "None recorded",
    description: "First payment column when no invoice id was stored",
  },
  ruleKeepOnReturn: {
    id: "console.founding.ruleKeepOnReturn",
    defaultMessage: "Churn rule: an organisation that cancels keeps its place whenever it returns.",
    description: "Churn rule keep_on_return",
  },
  ruleLoseOnCancel: {
    id: "console.founding.ruleLoseOnCancel",
    defaultMessage: "Churn rule: an organisation that cancels loses its place.",
    description: "Churn rule lose_on_cancel",
  },
  ruleWithinDays: {
    id: "console.founding.ruleWithinDays",
    defaultMessage:
      "Churn rule: an organisation that cancels keeps its place if it returns within {days, plural, one {# day} other {# days}}.",
    description: "Churn rule keep_if_returns_within_days",
  },
  refundRule: {
    id: "console.founding.refundRule",
    defaultMessage:
      "{hours, plural, =0 {A refunded first payment doesn't release the place.} one {A first payment refunded within # hour releases the place.} other {A first payment refunded within # hours releases the place.}}",
    description: "Refund release window",
  },
  export: {
    id: "console.founding.export",
    defaultMessage: "Export CSV",
    description: "Link: download every founding slot as CSV",
  },
  slotsCaption: {
    id: "console.founding.slotsCaption",
    defaultMessage: "Founding places",
    description: "Caption of the slots table",
  },
  number: { id: "console.founding.number", defaultMessage: "No.", description: "Column" },
  organisation: {
    id: "console.founding.organisation",
    defaultMessage: "Organisation",
    description: "Column",
  },
  allocatedAt: {
    id: "console.founding.allocatedAt",
    defaultMessage: "Given on",
    description: "Column: when the place was given",
  },
  payment: {
    id: "console.founding.payment",
    defaultMessage: "First payment",
    description: "Column: Stripe invoice id",
  },
  state: { id: "console.founding.state", defaultMessage: "Status", description: "Column" },
  actions: { id: "console.founding.actions", defaultMessage: "Actions", description: "Column" },
  stateActive: {
    id: "console.founding.stateActive",
    defaultMessage: "Active",
    description: "Slot state",
  },
  stateCancelled: {
    id: "console.founding.stateCancelled",
    defaultMessage: "Cancelled — may return",
    description: "Slot state: the organisation cancelled; the churn rule decides on return",
  },
  stateReleased: {
    id: "console.founding.stateReleased",
    defaultMessage: "Released ({reason})",
    description: "Slot state with the release reason",
  },
  reasonCancelled: {
    id: "console.founding.reasonCancelled",
    defaultMessage: "cancelled",
    description: "Release reason",
  },
  reasonNotReturned: {
    id: "console.founding.reasonNotReturned",
    defaultMessage: "didn't return in time",
    description: "Release reason",
  },
  reasonRefunded: {
    id: "console.founding.reasonRefunded",
    defaultMessage: "first payment refunded",
    description: "Release reason",
  },
  reasonAdmin: {
    id: "console.founding.reasonAdmin",
    defaultMessage: "released by Numo9",
    description: "Release reason",
  },
  release: {
    id: "console.founding.release",
    defaultMessage: "Release",
    description: "Button: release a founding slot",
  },
  releaseLabel: {
    id: "console.founding.releaseLabel",
    defaultMessage: "Release place {number} ({name})",
    description: "Accessible name of the release button",
  },
  releaseTitle: {
    id: "console.founding.releaseTitle",
    defaultMessage: "Release founding place {number}?",
    description: "Release dialog title",
  },
  releaseBody: {
    id: "console.founding.releaseBody",
    defaultMessage:
      "{name} loses founding status and keeps only its package's products. Number {number} is never given again. This is recorded in the audit log with your reason.",
    description: "Release dialog text",
  },
  reason: {
    id: "console.founding.reason",
    defaultMessage: "Reason",
    description: "Field label: why the slot is released",
  },
  reasonHint: {
    id: "console.founding.reasonHint",
    defaultMessage: "At least 5 characters, e.g. 'Duplicate account of Maple Bakery'.",
    description: "Field hint",
  },
  reasonTooShort: {
    id: "console.founding.reasonTooShort",
    defaultMessage: "Enter a reason of at least 5 characters.",
    description: "Validation",
  },
  cancel: { id: "console.founding.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "console.founding.close", defaultMessage: "Close", description: "Dialog close" },
  released: {
    id: "console.founding.released",
    defaultMessage: "Place {number} released.",
    description: "Status after a release",
  },
  releaseFailed: {
    id: "console.founding.releaseFailed",
    defaultMessage: "The place wasn't released. Try again.",
    description: "Release error",
  },
  forbidden: {
    id: "console.founding.forbidden",
    defaultMessage: "Only platform owners can release a place.",
    description: "Release refused (403)",
  },
  empty: {
    id: "console.founding.empty",
    defaultMessage: "No founding place given yet",
    description: "Empty state title",
  },
  emptyBody: {
    id: "console.founding.emptyBody",
    defaultMessage: "Places are given on an organisation's first successful payment.",
    description: "Empty state text",
  },
  loadFailed: {
    id: "console.founding.loadFailed",
    defaultMessage: "The founding offer didn't load",
    description: "Error state",
  },
  retry: { id: "console.founding.retry", defaultMessage: "Try again", description: "Button" },
});
