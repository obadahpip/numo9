import { defineMessages } from "@/i18n";

/** Recurring journals screen (C-04-T11). */
export const rm = defineMessages({
  title: {
    id: "journals.recurring.title",
    defaultMessage: "Recurring journals",
    description: "Heading",
  },
  add: {
    id: "journals.recurring.add",
    defaultMessage: "New recurring journal",
    description: "Button",
  },
  emptyTitle: {
    id: "journals.recurring.emptyTitle",
    defaultMessage: "No recurring journals yet",
    description: "Empty state",
  },
  emptyBody: {
    id: "journals.recurring.emptyBody",
    defaultMessage:
      "Rent, accruals, amortisation: set them up once and Numo9 writes them on schedule.",
    description: "Empty state text",
  },
  loadFailed: {
    id: "journals.recurring.loadFailed",
    defaultMessage: "Recurring journals couldn't load.",
    description: "Error state",
  },
  retry: { id: "journals.recurring.retry", defaultMessage: "Try again", description: "Retry" },
  name: { id: "journals.recurring.name", defaultMessage: "Name", description: "Field / column" },
  narration: {
    id: "journals.recurring.narration",
    defaultMessage: "Narration",
    description: "Field",
  },
  schedule: {
    id: "journals.recurring.schedule",
    defaultMessage: "Schedule",
    description: "Field group / column",
  },
  nextRun: { id: "journals.recurring.nextRun", defaultMessage: "Next run", description: "Column" },
  mode: {
    id: "journals.recurring.mode",
    defaultMessage: "Each time",
    description: "Field: draft or post",
  },
  modeName: {
    id: "journals.recurring.modeName",
    defaultMessage: "{mode, select, post {Post the journal} other {Save a draft}}",
    description: "What each occurrence becomes",
  },
  every: {
    id: "journals.recurring.every",
    defaultMessage:
      "{frequency, select, weekly {{n, plural, one {Every week} other {Every # weeks}}} quarterly {{n, plural, one {Every quarter} other {Every # quarters}}} yearly {{n, plural, one {Every year} other {Every # years}}} other {{n, plural, one {Every month} other {Every # months}}}}",
    description: "Schedule summary in the list",
  },
  paused: { id: "journals.recurring.paused", defaultMessage: "Paused", description: "Badge" },
  finished: {
    id: "journals.recurring.finished",
    defaultMessage: "Finished",
    description: "No next run",
  },
  newTitle: {
    id: "journals.recurring.newTitle",
    defaultMessage: "New recurring journal",
    description: "Editor heading",
  },
  editTitle: {
    id: "journals.recurring.editTitle",
    defaultMessage: "Edit {name}",
    description: "Editor heading",
  },
  repeatEvery: {
    id: "journals.recurring.repeatEvery",
    defaultMessage: "Repeat every",
    description: "Field",
  },
  unit: {
    id: "journals.recurring.unit",
    defaultMessage: "Unit",
    description: "Field: weeks, months…",
  },
  unitName: {
    id: "journals.recurring.unitName",
    defaultMessage:
      "{frequency, select, weekly {Weeks} quarterly {Quarters} yearly {Years} other {Months}}",
    description: "Option of the schedule unit",
  },
  start: { id: "journals.recurring.start", defaultMessage: "Starts on", description: "Field" },
  end: { id: "journals.recurring.end", defaultMessage: "Ends on (optional)", description: "Field" },
  nextDates: {
    id: "journals.recurring.nextDates",
    defaultMessage: "Next {count} dates",
    description: "Heading of the schedule preview",
  },
  noDates: {
    id: "journals.recurring.noDates",
    defaultMessage: "No date left in this schedule.",
    description: "Preview with nothing to come",
  },
  previewFailed: {
    id: "journals.recurring.previewFailed",
    defaultMessage: "The schedule couldn't be previewed.",
    description: "Preview error",
  },
  lines: { id: "journals.recurring.lines", defaultMessage: "Lines", description: "Table caption" },
  account: { id: "journals.recurring.account", defaultMessage: "Account", description: "Column" },
  debit: { id: "journals.recurring.debit", defaultMessage: "Debit", description: "Column" },
  credit: { id: "journals.recurring.credit", defaultMessage: "Credit", description: "Column" },
  description: {
    id: "journals.recurring.description",
    defaultMessage: "Description",
    description: "Column",
  },
  accountOfLine: {
    id: "journals.recurring.accountOfLine",
    defaultMessage: "Account, line {line}",
    description: "Cell",
  },
  debitOfLine: {
    id: "journals.recurring.debitOfLine",
    defaultMessage: "Debit, line {line}",
    description: "Cell",
  },
  creditOfLine: {
    id: "journals.recurring.creditOfLine",
    defaultMessage: "Credit, line {line}",
    description: "Cell",
  },
  descriptionOfLine: {
    id: "journals.recurring.descriptionOfLine",
    defaultMessage: "Description, line {line}",
    description: "Cell",
  },
  addLine: {
    id: "journals.recurring.addLine",
    defaultMessage: "Add a line",
    description: "Button",
  },
  balanced: {
    id: "journals.recurring.balanced",
    defaultMessage: "Balanced",
    description: "Lines balance",
  },
  outOfBalance: {
    id: "journals.recurring.outOfBalance",
    defaultMessage: "Out of balance by {amount}",
    description: "Lines don't balance",
  },
  lastRuns: {
    id: "journals.recurring.lastRuns",
    defaultMessage: "Last runs",
    description: "Heading",
  },
  createdOn: {
    id: "journals.recurring.createdOn",
    defaultMessage: "{date} — journal created",
    description: "A run of the schedule that created its journal",
  },
  skippedOn: {
    id: "journals.recurring.skippedOn",
    defaultMessage: "{date} — skipped: {reason}",
    description: "A run of the schedule that was skipped, with the reason",
  },
  save: { id: "journals.recurring.save", defaultMessage: "Save", description: "Button" },
  saveFailed: {
    id: "journals.recurring.saveFailed",
    defaultMessage: "The recurring journal couldn't be saved.",
    description: "Error",
  },
  pause: { id: "journals.recurring.pause", defaultMessage: "Pause", description: "Button" },
  resume: { id: "journals.recurring.resume", defaultMessage: "Resume", description: "Button" },
  close: { id: "journals.recurring.close", defaultMessage: "Close", description: "Button" },
});
