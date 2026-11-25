import { defineMessages } from "@/i18n";

/** Period close and year-end (C-06-T08, T09). */
export const pm = defineMessages({
  title: { id: "periodClose.title", defaultMessage: "Period close", description: "Page heading" },
  intro: {
    id: "periodClose.intro",
    defaultMessage:
      "Close each module month by month: a closed month can't take new postings. The year-end close moves the year's profit or loss to retained earnings in each book.",
    description: "Text under the heading",
  },
  year: {
    id: "periodClose.year",
    defaultMessage: "Fiscal year {start} – {end}",
    description: "The fiscal year shown",
  },
  previousYear: {
    id: "periodClose.previousYear",
    defaultMessage: "Previous year",
    description: "Button",
  },
  nextYear: { id: "periodClose.nextYear", defaultMessage: "Next year", description: "Button" },
  grid: {
    id: "periodClose.grid",
    defaultMessage: "Close status by module and month",
    description: "Accessible name of the timeline (arrow keys move between months)",
  },
  module: { id: "periodClose.module", defaultMessage: "Module", description: "Column header" },
  status: {
    id: "periodClose.status",
    defaultMessage: "{status, select, closed {Closed} locked {Locked} other {Open}}",
    description: "Status pill of a month",
  },
  cell: {
    id: "periodClose.cell",
    defaultMessage: "{module}, {month}: {status}",
    description: "Accessible name of a month cell",
  },
  checklistTitle: {
    id: "periodClose.checklistTitle",
    defaultMessage: "{module} — {month}",
    description: "Heading of the checklist panel",
  },
  checklistIntro: {
    id: "periodClose.checklistIntro",
    defaultMessage: "Before closing, review what is still open in the month.",
    description: "Checklist text",
  },
  itemCount: {
    id: "periodClose.itemCount",
    defaultMessage: "{label}: {count}",
    description: "A checklist item with its count",
  },
  review: { id: "periodClose.review", defaultMessage: "Review", description: "Checklist link" },
  close: { id: "periodClose.close", defaultMessage: "Close {month}", description: "Button" },
  closeTitle: {
    id: "periodClose.closeTitle",
    defaultMessage: "Close {module} to {date}?",
    description: "Close dialog title",
  },
  closeBody: {
    id: "periodClose.closeBody",
    defaultMessage:
      "Nothing dated on or before {date} can be posted in {module} any more — for everyone, advisers included — until an adviser reopens it with a reason.",
    description: "Close dialog consequences",
  },
  confirmClose: {
    id: "periodClose.confirmClose",
    defaultMessage: "Close the period",
    description: "Button",
  },
  reopen: { id: "periodClose.reopen", defaultMessage: "Reopen", description: "Button" },
  reopenTitle: {
    id: "periodClose.reopenTitle",
    defaultMessage: "Reopen {module} to {date}?",
    description: "Reopen dialog title",
  },
  reopenBody: {
    id: "periodClose.reopenBody",
    defaultMessage:
      "Postings dated in the reopened months are allowed again. The lock goes back to what it was before this close.",
    description: "Reopen dialog consequences",
  },
  reopenYearBody: {
    id: "periodClose.reopenYearBody",
    defaultMessage:
      "The year-end closing journals are reversed: revenue and expenses are back on the income statement and retained earnings as before.",
    description: "Reopen dialog: extra consequences of a year-end",
  },
  reason: {
    id: "periodClose.reason",
    defaultMessage: "Why is it reopened? (kept in the audit log)",
    description: "Reopen reason field",
  },
  confirmReopen: {
    id: "periodClose.confirmReopen",
    defaultMessage: "Reopen the period",
    description: "Button",
  },
  adviserOnly: {
    id: "periodClose.adviserOnly",
    defaultMessage: "Only your accountant (an adviser) can reopen a closed period.",
    description: "Hint instead of Reopen",
  },
  yearEnd: {
    id: "periodClose.yearEnd",
    defaultMessage: "Close the fiscal year",
    description: "Button",
  },
  yearEndTitle: {
    id: "periodClose.yearEndTitle",
    defaultMessage: "Close the fiscal year ending {date}?",
    description: "Year-end dialog title",
  },
  yearEndBody: {
    id: "periodClose.yearEndBody",
    defaultMessage:
      "A closing journal per book (accounting and tax) moves the year's revenue and expenses to retained earnings, dated {date}, and the general ledger is closed to that date.",
    description: "Year-end dialog consequences",
  },
  yearClosed: {
    id: "periodClose.yearClosed",
    defaultMessage: "The fiscal year is closed (closing journals {numbers}).",
    description: "Year-end status",
  },
  cancel: { id: "periodClose.cancel", defaultMessage: "Cancel", description: "Button" },
  closeDialog: {
    id: "periodClose.closeDialog",
    defaultMessage: "Close",
    description: "Dialog close",
  },
  saved: { id: "periodClose.saved", defaultMessage: "Saved.", description: "Status" },
  failed: {
    id: "periodClose.failed",
    defaultMessage: "That didn't work and nothing was changed. Try again in a moment.",
    description: "Error",
  },
  loading: { id: "periodClose.loading", defaultMessage: "Loading…", description: "Placeholder" },
});
