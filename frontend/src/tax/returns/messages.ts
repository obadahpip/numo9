import { defineMessages } from "@/i18n";

/** The GST/HST return worksheet and list (G-03-T11, T12). */
export const retm = defineMessages({
  listTitle: {
    id: "tax.returns.listTitle",
    defaultMessage: "GST/HST returns",
    description: "Heading of the returns page",
  },
  listIntro: {
    id: "tax.returns.listIntro",
    defaultMessage:
      "Prepare a return from the books for a filing period, have someone else review it, then mark it as filed with the confirmation number the CRA gave you.",
    description: "Text under the returns heading",
  },
  registration: {
    id: "tax.returns.registration",
    defaultMessage: "Registration",
    description: "Label of the registration choice",
  },
  noRegistration: {
    id: "tax.returns.noRegistration",
    defaultMessage: "Add a GST/HST registration in the tax settings to prepare returns.",
    description: "Empty state when the organisation has no GST/HST registration",
  },
  period: { id: "tax.returns.period", defaultMessage: "Period", description: "Column heading" },
  due: { id: "tax.returns.due", defaultMessage: "Due", description: "Column heading" },
  version: {
    id: "tax.returns.version",
    defaultMessage: "Version {version}",
    description: "The version of a return",
  },
  status: {
    id: "tax.returns.status",
    defaultMessage:
      "{status, select, draft {Draft} reviewed {Reviewed} filed {Filed} amended {Amended} other {Not started}}",
    description: "Status of a return",
  },
  statusHeading: {
    id: "tax.returns.statusHeading",
    defaultMessage: "Status",
    description: "Column heading",
  },
  actionsHeading: {
    id: "tax.returns.actionsHeading",
    defaultMessage: "Actions",
    description: "Column heading (screen readers)",
  },
  open: { id: "tax.returns.open", defaultMessage: "Open", description: "Opens a return" },
  prepare: {
    id: "tax.returns.prepare",
    defaultMessage: "Prepare return",
    description: "Prepares the period's return from the books",
  },
  noPeriods: {
    id: "tax.returns.noPeriods",
    defaultMessage: "This registration has no filing periods yet.",
    description: "Empty state",
  },
  loadFailed: {
    id: "tax.returns.loadFailed",
    defaultMessage: "The return couldn't be loaded.",
    description: "Error state",
  },
  retry: { id: "tax.returns.retry", defaultMessage: "Try again", description: "Retry button" },
  // ---- worksheet (T11)
  worksheetTitle: {
    id: "tax.returns.worksheetTitle",
    defaultMessage: "GST/HST return {period}",
    description: "Heading of the worksheet",
  },
  meta: {
    id: "tax.returns.meta",
    defaultMessage:
      "Version {version} · {method, select, quick {Quick method} other {Regular method}} · {status, select, draft {Draft} reviewed {Reviewed} filed {Filed} amended {Amended} other {Draft}}",
    description: "Version, method and status under the worksheet heading",
  },
  people: {
    id: "tax.returns.people",
    defaultMessage: "Prepared by {prepared} · reviewed by {reviewed}",
    description: "Who prepared and reviewed the return",
  },
  range: {
    id: "tax.returns.range",
    defaultMessage: "{start} – {end}",
    description: "A period's first and last day",
  },
  statusVersion: {
    id: "tax.returns.statusVersion",
    defaultMessage:
      "{status, select, draft {Draft} reviewed {Reviewed} filed {Filed} amended {Amended} other {Not started}} · version {version}",
    description: "Status of an amended return with its version",
  },
  method: {
    id: "tax.returns.method",
    defaultMessage: "{method, select, quick {Quick method} other {Regular method}}",
    description: "The method of the return",
  },
  steps: {
    id: "tax.returns.steps",
    defaultMessage: "Progress of the return",
    description: "Accessible name of the stepper",
  },
  step: {
    id: "tax.returns.step",
    defaultMessage: "{step, select, draft {Prepare} reviewed {Review} other {File}}",
    description: "A step of the return",
  },
  stepDone: {
    id: "tax.returns.stepDone",
    defaultMessage: "{label} (done)",
    description: "Screen-reader label of a finished step",
  },
  stepCurrent: {
    id: "tax.returns.stepCurrent",
    defaultMessage: "{label} (current step)",
    description: "Screen-reader label of the current step",
  },
  line: { id: "tax.returns.line", defaultMessage: "Line", description: "Column heading" },
  description: {
    id: "tax.returns.description",
    defaultMessage: "Description",
    description: "Column heading",
  },
  amount: { id: "tax.returns.amount", defaultMessage: "Amount", description: "Column heading" },
  lineNumber: {
    id: "tax.returns.lineNumber",
    defaultMessage: "Line {line}",
    description: "A line of the return",
  },
  showDocuments: {
    id: "tax.returns.showDocuments",
    defaultMessage: "Show the documents behind line {line}",
    description: "Opens the drill-down drawer",
  },
  entryLabel: {
    id: "tax.returns.entryLabel",
    defaultMessage: "Amount for line {line}",
    description: "Accessible name of an entry field",
  },
  changedTitle: {
    id: "tax.returns.changedTitle",
    defaultMessage: "The books changed since this return was calculated",
    description: "Heading of the changed-since banner",
  },
  changedLine: {
    id: "tax.returns.changedLine",
    defaultMessage: "Line {line}: {was} → {now}",
    description: "A changed line in the banner",
  },
  recalculate: {
    id: "tax.returns.recalculate",
    defaultMessage: "Recalculate",
    description: "Recalculates the return from the books",
  },
  saveEntries: {
    id: "tax.returns.saveEntries",
    defaultMessage: "Save amounts",
    description: "Saves the typed amounts and recalculates",
  },
  recalculated: {
    id: "tax.returns.recalculated",
    defaultMessage: "Return recalculated from the books.",
    description: "Notice",
  },
  review: {
    id: "tax.returns.review",
    defaultMessage: "Mark as reviewed",
    description: "Marks the return reviewed",
  },
  reviewHint: {
    id: "tax.returns.reviewHint",
    defaultMessage: "Someone other than the person who prepared the return reviews it.",
    description: "Hint next to the review button",
  },
  reviewed: {
    id: "tax.returns.reviewed",
    defaultMessage: "Return marked as reviewed.",
    description: "Notice",
  },
  sendBack: {
    id: "tax.returns.sendBack",
    defaultMessage: "Send back",
    description: "Sends a reviewed return back to draft",
  },
  sendBackReason: {
    id: "tax.returns.sendBackReason",
    defaultMessage: "Why does it go back?",
    description: "Label of the send-back reason",
  },
  sentBack: {
    id: "tax.returns.sentBack",
    defaultMessage: "Return sent back to draft.",
    description: "Notice",
  },
  preparedBy: {
    id: "tax.returns.preparedBy",
    defaultMessage: "Prepared by {name}",
    description: "Who prepared the return",
  },
  reviewedBy: {
    id: "tax.returns.reviewedBy",
    defaultMessage: "Reviewed by {name}",
    description: "Who reviewed the return",
  },
  exportPdf: { id: "tax.returns.exportPdf", defaultMessage: "PDF", description: "Download" },
  exportCsv: { id: "tax.returns.exportCsv", defaultMessage: "CSV", description: "Download" },
  backToList: {
    id: "tax.returns.backToList",
    defaultMessage: "All returns",
    description: "Link back to the returns list",
  },
  // ---- drill-down drawer
  drillTitle: {
    id: "tax.returns.drillTitle",
    defaultMessage: "Line {line}: {label}",
    description: "Heading of the drill-down drawer",
  },
  drillIntro: {
    id: "tax.returns.drillIntro",
    defaultMessage: "The documents behind this line; their amounts add up to the line.",
    description: "Text in the drill-down drawer",
  },
  drillEmpty: {
    id: "tax.returns.drillEmpty",
    defaultMessage: "No documents make up this line.",
    description: "Empty drill-down",
  },
  drillTotal: { id: "tax.returns.drillTotal", defaultMessage: "Total", description: "Total row" },
  document: {
    id: "tax.returns.document",
    defaultMessage: "Document",
    description: "Column heading",
  },
  date: { id: "tax.returns.date", defaultMessage: "Date", description: "Column heading" },
  contact: { id: "tax.returns.contact", defaultMessage: "Contact", description: "Column heading" },
  close: { id: "tax.returns.close", defaultMessage: "Close", description: "Close button" },
  cancel: { id: "tax.returns.cancel", defaultMessage: "Cancel", description: "Cancel button" },
  lateAdjustment: {
    id: "tax.returns.lateAdjustment",
    defaultMessage: "Late adjustment from {period}",
    description: "A late adjustment carried into the period",
  },
  // ---- filing, locks and amendments (T12)
  markFiled: {
    id: "tax.returns.markFiled",
    defaultMessage: "Mark as filed",
    description: "Opens the mark-as-filed dialog",
  },
  fileTitle: {
    id: "tax.returns.fileTitle",
    defaultMessage: "Mark the return as filed",
    description: "Heading of the mark-as-filed dialog",
  },
  fileIntro: {
    id: "tax.returns.fileIntro",
    defaultMessage:
      "File the return with the CRA, then record the confirmation number here. The period is then locked for tax: changes that touch its sales tax go to the next open period as late adjustments.",
    description: "Text in the mark-as-filed dialog",
  },
  confirmationNo: {
    id: "tax.returns.confirmationNo",
    defaultMessage: "Confirmation number",
    description: "Field label",
  },
  filedOn: { id: "tax.returns.filedOn", defaultMessage: "Filed on", description: "Field label" },
  filed: {
    id: "tax.returns.filed",
    defaultMessage: "Return marked as filed. The period is locked.",
    description: "Notice",
  },
  filedSummary: {
    id: "tax.returns.filedSummary",
    defaultMessage: "Filed on {date} · confirmation {number}",
    description: "Summary of a filed return",
  },
  locked: {
    id: "tax.returns.locked",
    defaultMessage: "Locked: filed",
    description: "Accessible name of the lock icon of a filed period",
  },
  amend: {
    id: "tax.returns.amend",
    defaultMessage: "Amend",
    description: "Opens the amend dialog",
  },
  amendTitle: {
    id: "tax.returns.amendTitle",
    defaultMessage: "Amend the filed return",
    description: "Heading of the amend dialog",
  },
  amendIntro: {
    id: "tax.returns.amendIntro",
    defaultMessage:
      "An amendment is a new version of the return, starting as a draft. The filed version stays as it was and is marked amended once the new one is filed.",
    description: "Text in the amend dialog",
  },
  amendReason: {
    id: "tax.returns.amendReason",
    defaultMessage: "Why is it amended?",
    description: "Field label",
  },
  amended: {
    id: "tax.returns.amended",
    defaultMessage: "Amendment started as version {version}.",
    description: "Notice",
  },
  notCurrent: {
    id: "tax.returns.notCurrent",
    defaultMessage: "This is an earlier version of the return.",
    description: "Banner on an earlier version",
  },
  openCurrent: {
    id: "tax.returns.openCurrent",
    defaultMessage: "Open the current version",
    description: "Link to the current version",
  },
  versions: {
    id: "tax.returns.versions",
    defaultMessage: "Versions",
    description: "Heading of the versions list",
  },
  required: {
    id: "tax.returns.required",
    defaultMessage: "Required",
    description: "Field error",
  },
});
