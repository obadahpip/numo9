import { defineMessages } from "@/i18n";

/** Recurring invoices (D-04-T08…T10): the template editor, its preview, the list and history. */
export const rim = defineMessages({
  newTitle: {
    id: "sales.recurring.newTitle",
    defaultMessage: "New recurring invoice",
    description: "Heading of the template editor for a new template",
  },
  title: {
    id: "sales.recurring.title",
    defaultMessage: "Recurring invoice {name}",
    description: "Heading of a saved template",
  },
  form: {
    id: "sales.recurring.form",
    defaultMessage: "Recurring invoice details",
    description: "Name of the header fields group",
  },
  name: { id: "sales.recurring.name", defaultMessage: "Name", description: "Field" },
  nameHint: {
    id: "sales.recurring.nameHint",
    defaultMessage: "For you only, e.g. Monthly bookkeeping for Maple Leaf.",
    description: "Hint under the template name",
  },
  customer: { id: "sales.recurring.customer", defaultMessage: "Customer", description: "Field" },
  chooseCustomer: {
    id: "sales.recurring.chooseCustomer",
    defaultMessage: "Choose a customer",
    description: "Customer placeholder",
  },
  reference: {
    id: "sales.recurring.reference",
    defaultMessage: "Reference",
    description: "Field",
  },
  taxMode: {
    id: "sales.recurring.taxMode",
    defaultMessage: "Amounts are",
    description: "Tax mode field",
  },
  taxExclusive: {
    id: "sales.recurring.taxExclusive",
    defaultMessage: "Tax exclusive",
    description: "Tax mode option",
  },
  taxInclusive: {
    id: "sales.recurring.taxInclusive",
    defaultMessage: "Tax inclusive",
    description: "Tax mode option",
  },
  taxNone: { id: "sales.recurring.taxNone", defaultMessage: "No tax", description: "Option" },
  notes: { id: "sales.recurring.notes", defaultMessage: "Notes", description: "Field" },
  placeholders: {
    id: "sales.recurring.placeholders",
    defaultMessage:
      "Placeholders in the reference, notes and line descriptions are filled in on each invoice:",
    description: "Hint listing the placeholders the generator resolves",
  },
  unknownPlaceholders: {
    id: "sales.recurring.unknownPlaceholders",
    defaultMessage: "Not a placeholder, left as typed: {names}",
    description: "Warning: a typo in a placeholder name",
  },
  schedule: {
    id: "sales.recurring.schedule",
    defaultMessage: "Schedule",
    description: "Schedule panel heading",
  },
  repeatEvery: {
    id: "sales.recurring.repeatEvery",
    defaultMessage: "Repeat every",
    description: "Schedule interval field",
  },
  unit: { id: "sales.recurring.unit", defaultMessage: "Period", description: "Schedule unit" },
  unitName: {
    id: "sales.recurring.unitName",
    defaultMessage:
      "{frequency, select, weekly {week(s)} monthly {month(s)} quarterly {quarter(s)} other {year(s)}}",
    description: "Schedule unit option",
  },
  every: {
    id: "sales.recurring.every",
    defaultMessage:
      "{frequency, select, weekly {Every {n, plural, one {week} other {# weeks}}} monthly {Every {n, plural, one {month} other {# months}}} quarterly {Every {n, plural, one {quarter} other {# quarters}}} other {Every {n, plural, one {year} other {# years}}}}",
    description: "A template's schedule in the list",
  },
  start: {
    id: "sales.recurring.start",
    defaultMessage: "First invoice on",
    description: "Schedule start date field",
  },
  end: {
    id: "sales.recurring.end",
    defaultMessage: "Last invoice by (optional)",
    description: "Schedule end date field",
  },
  nextDates: {
    id: "sales.recurring.nextDates",
    defaultMessage: "Next {count} invoice dates",
    description: "Heading of the schedule's next dates",
  },
  noDates: {
    id: "sales.recurring.noDates",
    defaultMessage: "No more dates: the schedule has ended.",
    description: "Schedule has no future dates",
  },
  dueRule: {
    id: "sales.recurring.dueRule",
    defaultMessage: "Each invoice is due by the customer's payment terms.",
    description: "Due-date rule hint",
  },
  mode: {
    id: "sales.recurring.mode",
    defaultMessage: "On each date",
    description: "Mode radio group legend",
  },
  modeName: {
    id: "sales.recurring.modeName",
    defaultMessage:
      "{mode, select, draft {Save as a draft} approve {Approve} other {Approve and send}}",
    description: "Mode option and list cell",
  },
  modeHint: {
    id: "sales.recurring.modeHint",
    defaultMessage:
      "{mode, select, draft {The invoice waits in Drafts for you to check and approve.} approve {The invoice is approved and posted, with its number.} other {The invoice is approved, posted and emailed to the customer.}}",
    description: "What each mode does",
  },
  prorate: {
    id: "sales.recurring.prorate",
    defaultMessage: "Prorate a partial first or last period by days",
    description: "Proration checkbox",
  },
  serviceStart: {
    id: "sales.recurring.serviceStart",
    defaultMessage: "Service starts",
    description: "Proration field",
  },
  serviceEnd: {
    id: "sales.recurring.serviceEnd",
    defaultMessage: "Service ends",
    description: "Proration field",
  },
  prorateHint: {
    id: "sales.recurring.prorateHint",
    defaultMessage:
      "A period the service covers only in part is charged for the days covered, line by line.",
    description: "Proration hint",
  },
  save: { id: "sales.recurring.save", defaultMessage: "Save", description: "Button" },
  saving: { id: "sales.recurring.saving", defaultMessage: "Saving…", description: "Busy button" },
  saved: {
    id: "sales.recurring.saved",
    defaultMessage: "Recurring invoice saved. Changes apply to the next invoices only.",
    description: "Notice after saving",
  },
  saveFailed: {
    id: "sales.recurring.saveFailed",
    defaultMessage: "The recurring invoice wasn't saved.",
    description: "Generic save error",
  },
  pause: { id: "sales.recurring.pause", defaultMessage: "Pause", description: "Button" },
  resume: { id: "sales.recurring.resume", defaultMessage: "Resume", description: "Button" },
  pausedNotice: {
    id: "sales.recurring.pausedNotice",
    defaultMessage: "Paused: its dates are skipped until you resume it.",
    description: "Notice on a paused template",
  },
  status: {
    id: "sales.recurring.status",
    defaultMessage: "{status, select, active {Active} paused {Paused} other {Ended}}",
    description: "Template status badge",
  },
  loadFailed: {
    id: "sales.recurring.loadFailed",
    defaultMessage: "The recurring invoice couldn't be loaded.",
    description: "Load error",
  },
  retry: { id: "sales.recurring.retry", defaultMessage: "Try again", description: "Button" },
  previewTitle: {
    id: "sales.recurring.previewTitle",
    defaultMessage: "Preview next invoice",
    description: "Heading of the preview panel",
  },
  previewDate: {
    id: "sales.recurring.previewDate",
    defaultMessage: "For",
    description: "Label of the occurrence date picker in the preview",
  },
  previewFailed: {
    id: "sales.recurring.previewFailed",
    defaultMessage: "The next invoice couldn't be previewed.",
    description: "Preview error",
  },
  previewNone: {
    id: "sales.recurring.previewNone",
    defaultMessage: "The schedule has ended: there's no next invoice.",
    description: "Preview of an ended template",
  },
  previewSkipped: {
    id: "sales.recurring.previewSkipped",
    defaultMessage: "This date will be skipped: {reason}",
    description: "Preview warning: the occurrence would be skipped",
  },
  previewCustomer: {
    id: "sales.recurring.previewCustomer",
    defaultMessage: "Customer",
    description: "Preview field",
  },
  previewInvoiceDate: {
    id: "sales.recurring.previewInvoiceDate",
    defaultMessage: "Invoice date",
    description: "Preview field",
  },
  previewDue: {
    id: "sales.recurring.previewDue",
    defaultMessage: "Due date",
    description: "Preview field",
  },
  previewPeriod: {
    id: "sales.recurring.previewPeriod",
    defaultMessage: "Period billed",
    description: "Preview field",
  },
  previewPeriodValue: {
    id: "sales.recurring.previewPeriodValue",
    defaultMessage: "{start} to {end}",
    description: "The period an invoice bills",
  },
  previewProrated: {
    id: "sales.recurring.previewProrated",
    defaultMessage: "Prorated: {covered} of {days} days",
    description: "Badge on a prorated preview",
  },
  previewLines: {
    id: "sales.recurring.previewLines",
    defaultMessage: "Lines of the next invoice",
    description: "Table caption",
  },
  previewDescription: {
    id: "sales.recurring.previewDescription",
    defaultMessage: "Description",
    description: "Column",
  },
  previewQuantity: {
    id: "sales.recurring.previewQuantity",
    defaultMessage: "Qty",
    description: "Column",
  },
  previewAmount: {
    id: "sales.recurring.previewAmount",
    defaultMessage: "Amount",
    description: "Column",
  },
  previewSubtotal: {
    id: "sales.recurring.previewSubtotal",
    defaultMessage: "Subtotal",
    description: "Preview total row",
  },
  previewTax: { id: "sales.recurring.previewTax", defaultMessage: "Tax", description: "Row" },
  previewTotal: {
    id: "sales.recurring.previewTotal",
    defaultMessage: "Total",
    description: "Preview total row",
  },
});
