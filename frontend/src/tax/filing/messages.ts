import { defineMessages, type MessageDescriptor } from "@/i18n";

import type { BlockState, Frequency, PeriodKind } from "./api";

export const fmsg = defineMessages({
  title: {
    id: "tax.filing.title",
    defaultMessage: "Filing periods",
    description: "Page heading: a registration's GST/HST or QST filing periods (G-03a)",
  },
  intro: {
    id: "tax.filing.intro",
    defaultMessage:
      "Every day of the registration belongs to exactly one period. Filed periods never change.",
    description: "Text under the filing periods heading",
  },
  registration: {
    id: "tax.filing.registration",
    defaultMessage: "Registration {number}",
    description: "Sub-heading with the registration number",
  },
  backToSettings: {
    id: "tax.filing.backToSettings",
    defaultMessage: "Tax registrations and settings",
    description: "Link from the filing periods back to the tax settings page (G-06-T09)",
  },
  timeline: {
    id: "tax.filing.timeline",
    defaultMessage: "Filing periods timeline",
    description: "Accessible name of the timeline",
  },
  period: {
    id: "tax.filing.period",
    defaultMessage: "Period {n}: {start} – {end}, {state}",
    description: "Accessible name of a period block",
  },
  periodDates: {
    id: "tax.filing.periodDates",
    defaultMessage: "{start} – {end}",
    description: "A period's dates",
  },
  sequence: {
    id: "tax.filing.sequence",
    defaultMessage: "Period {n}",
    description: "Hover card: sequence number",
  },
  returnDue: {
    id: "tax.filing.returnDue",
    defaultMessage: "Return due {date}",
    description: "Hover card: return due date",
  },
  returnDueRolled: {
    id: "tax.filing.returnDueRolled",
    defaultMessage: "Return due {date} *",
    description: "Hover card: return due date moved to the next business day (asterisk)",
  },
  kindState: {
    id: "tax.filing.kindState",
    defaultMessage: "{kind} · {state}",
    description: "Hover card: period kind and state",
  },
  paymentDue: {
    id: "tax.filing.paymentDue",
    defaultMessage: "Payment due {date}",
    description: "Hover card: payment due date",
  },
  rolledNote: {
    id: "tax.filing.rolledNote",
    defaultMessage: "* Moved to the next business day (weekend or holiday).",
    description: "Legend: what the asterisk on a due date means",
  },
  switchMarker: {
    id: "tax.filing.switchMarker",
    defaultMessage: "{frequency} from {date}",
    description: "Marker where a filing frequency takes effect",
  },
  legend: { id: "tax.filing.legend", defaultMessage: "Legend", description: "Legend name" },
  stateFiled: { id: "tax.filing.state.filed", defaultMessage: "Filed", description: "Status" },
  stateOpen: { id: "tax.filing.state.open", defaultMessage: "Open", description: "Status" },
  stateDueSoon: {
    id: "tax.filing.state.dueSoon",
    defaultMessage: "Due soon",
    description: "Status: return due within 14 days",
  },
  stateOverdue: {
    id: "tax.filing.state.overdue",
    defaultMessage: "Overdue",
    description: "Status: return past due",
  },
  kindRegular: { id: "tax.filing.kind.regular", defaultMessage: "Regular", description: "Kind" },
  kindCustom: {
    id: "tax.filing.kind.custom",
    defaultMessage: "Out of cycle",
    description: "Period kind",
  },
  kindStub: { id: "tax.filing.kind.stub", defaultMessage: "Stub", description: "Period kind" },
  monthly: { id: "tax.filing.frequency.monthly", defaultMessage: "Monthly", description: "Freq." },
  quarterly: {
    id: "tax.filing.frequency.quarterly",
    defaultMessage: "Quarterly",
    description: "Frequency",
  },
  annual: { id: "tax.filing.frequency.annual", defaultMessage: "Annual", description: "Freq." },
  noPeriods: {
    id: "tax.filing.noPeriods",
    defaultMessage: "No filing periods yet",
    description: "Empty state title",
  },
  noPeriodsBody: {
    id: "tax.filing.noPeriodsBody",
    defaultMessage: "Choose how often this registration files to create its periods.",
    description: "Empty state text",
  },
  loadFailed: {
    id: "tax.filing.loadFailed",
    defaultMessage: "The filing periods couldn't be loaded.",
    description: "Error state",
  },
  retry: { id: "tax.filing.retry", defaultMessage: "Try again", description: "Button" },
  changeFrequency: {
    id: "tax.filing.changeFrequency",
    defaultMessage: "Change frequency",
    description: "Button opening the wizard",
  },
  setFrequency: {
    id: "tax.filing.setFrequency",
    defaultMessage: "Choose filing frequency",
    description: "Button opening the wizard when there is no frequency yet",
  },
  addCustom: {
    id: "tax.filing.addCustom",
    defaultMessage: "Add out-of-cycle period",
    description: "Button opening the dialog",
  },
  close: { id: "tax.filing.close", defaultMessage: "Close", description: "Dialog close" },
  cancel: { id: "tax.filing.cancel", defaultMessage: "Cancel", description: "Button" },
  back: { id: "tax.filing.back", defaultMessage: "Back", description: "Wizard button" },
  next: { id: "tax.filing.next", defaultMessage: "Next", description: "Wizard button" },
  previewButton: {
    id: "tax.filing.previewButton",
    defaultMessage: "Preview",
    description: "Button: show the diff",
  },
  confirm: {
    id: "tax.filing.confirm",
    defaultMessage: "Confirm change",
    description: "Button: save the previewed change",
  },
  wizardTitle: {
    id: "tax.filing.wizard.title",
    defaultMessage: "Change filing frequency",
    description: "Wizard title",
  },
  wizardStep: {
    id: "tax.filing.wizard.step",
    defaultMessage: "Step {n} of {total}: {name}",
    description: "Wizard progress",
  },
  stepFrequency: {
    id: "tax.filing.wizard.stepFrequency",
    defaultMessage: "Frequency",
    description: "Wizard step",
  },
  stepDate: {
    id: "tax.filing.wizard.stepDate",
    defaultMessage: "Effective date",
    description: "Wizard step",
  },
  stepApproval: {
    id: "tax.filing.wizard.stepApproval",
    defaultMessage: "Approval",
    description: "Wizard step",
  },
  stepPreview: {
    id: "tax.filing.wizard.stepPreview",
    defaultMessage: "Preview",
    description: "Wizard step",
  },
  frequencyLabel: {
    id: "tax.filing.wizard.frequency",
    defaultMessage: "New filing frequency",
    description: "Field",
  },
  effectiveFrom: {
    id: "tax.filing.wizard.effectiveFrom",
    defaultMessage: "Takes effect on",
    description: "Field",
  },
  effectiveHelp: {
    id: "tax.filing.wizard.effectiveHelp",
    defaultMessage:
      "The first day of the new frequency. It can't fall inside a period already filed.",
    description: "Field help",
  },
  approvalRef: {
    id: "tax.filing.wizard.approvalRef",
    defaultMessage: "CRA or Revenu Québec approval reference",
    description: "Field",
  },
  approvalHelp: {
    id: "tax.filing.wizard.approvalHelp",
    defaultMessage: "Needed when the change doesn't start on the first day of a financial year.",
    description: "Field help",
  },
  approvalDate: {
    id: "tax.filing.wizard.approvalDate",
    defaultMessage: "Approval date",
    description: "Field",
  },
  note: { id: "tax.filing.note", defaultMessage: "Note", description: "Field" },
  diffTitle: {
    id: "tax.filing.diff.title",
    defaultMessage: "What changes",
    description: "Diff heading",
  },
  diffSummary: {
    id: "tax.filing.diff.summary",
    defaultMessage:
      "{removed, plural, =0 {No period removed} one {# period removed} other {# periods removed}}, {added, plural, =0 {none added} one {# added} other {# added}}, {changed, plural, =0 {none shortened} one {# shortened} other {# shortened}}. Filed periods and tax postings stay as they are.",
    description: "Counts under the diff",
  },
  diffRemovedRow: {
    id: "tax.filing.diff.removedRow",
    defaultMessage: "Removed: {start} – {end}",
    description: "Diff: a period the change removes",
  },
  diffAddedRow: {
    id: "tax.filing.diff.addedRow",
    defaultMessage: "Added: {start} – {end} · {kind}",
    description: "Diff: a period the change adds, with its kind",
  },
  diffChangedRow: {
    id: "tax.filing.diff.changedRow",
    defaultMessage: "Shortened: {start} – {before} becomes {start} – {after}",
    description: "Diff: a period cut where the change starts",
  },
  diffTable: {
    id: "tax.filing.diff.table",
    defaultMessage: "Periods removed, added and shortened",
    description: "Accessible name of the diff list",
  },
  noChange: {
    id: "tax.filing.diff.noChange",
    defaultMessage: "This change leaves every period as it is.",
    description: "Diff with nothing in it",
  },
  saved: {
    id: "tax.filing.saved",
    defaultMessage: "Filing periods updated",
    description: "Confirmation after a change",
  },
  failed: {
    id: "tax.filing.failed",
    defaultMessage: "The change couldn't be saved. Try again.",
    description: "Generic failure",
  },
  customTitle: {
    id: "tax.filing.custom.title",
    defaultMessage: "Add an out-of-cycle period",
    description: "Dialog title",
  },
  customBody: {
    id: "tax.filing.custom.body",
    defaultMessage:
      "For a return that doesn't follow the usual cycle, such as 1 January to 15 March after a year-end change.",
    description: "Dialog description",
  },
  customStart: { id: "tax.filing.custom.start", defaultMessage: "Starts", description: "Field" },
  customEnd: { id: "tax.filing.custom.end", defaultMessage: "Ends", description: "Field" },
  customNote: {
    id: "tax.filing.custom.note",
    defaultMessage: "Why (kept in the history)",
    description: "Field",
  },
  customRealign: {
    id: "tax.filing.custom.realign",
    defaultMessage:
      "Unfiled periods it overlaps are removed. Regular periods then restart on {date}, the day after it ends.",
    description: "Explanation of the realignment",
  },
  customOk: {
    id: "tax.filing.custom.ok",
    defaultMessage: "No filed period overlaps these dates.",
    description: "Check passed",
  },
  customSave: {
    id: "tax.filing.custom.save",
    defaultMessage: "Add period",
    description: "Button",
  },
  customDates: {
    id: "tax.filing.custom.dates",
    defaultMessage: "The period must end on or after the day it starts.",
    description: "Validation",
  },
  removeCustom: {
    id: "tax.filing.custom.remove",
    defaultMessage: "Remove out-of-cycle period {start} – {end}",
    description: "Button on a custom period",
  },
  historyTitle: {
    id: "tax.filing.history.title",
    defaultMessage: "Frequency history",
    description: "History panel heading",
  },
  historyTable: {
    id: "tax.filing.history.table",
    defaultMessage: "Filing frequency changes",
    description: "Accessible name of the history table",
  },
  historyFrom: { id: "tax.filing.history.from", defaultMessage: "From", description: "Column" },
  historyFrequency: {
    id: "tax.filing.history.frequency",
    defaultMessage: "Frequency",
    description: "Column",
  },
  historyApproval: {
    id: "tax.filing.history.approval",
    defaultMessage: "Approval",
    description: "Column",
  },
  historyBy: {
    id: "tax.filing.history.by",
    defaultMessage: "Changed by",
    description: "Column",
  },
  historyWhen: { id: "tax.filing.history.when", defaultMessage: "When", description: "Column" },
  historyApprovalOn: {
    id: "tax.filing.history.approvalOn",
    defaultMessage: "{ref} ({date})",
    description: "Approval reference and date",
  },
  historyNone: {
    id: "tax.filing.history.none",
    defaultMessage: "No frequency chosen yet.",
    description: "Empty history",
  },
  historySystem: {
    id: "tax.filing.history.system",
    defaultMessage: "System",
    description: "Author when no person recorded the change",
  },
  historyCurrent: {
    id: "tax.filing.history.current",
    defaultMessage: "Current",
    description: "Badge on the frequency in force today",
  },
});

export const frequencyLabels: Record<Frequency, MessageDescriptor> = {
  monthly: fmsg.monthly,
  quarterly: fmsg.quarterly,
  annual: fmsg.annual,
};

export const stateLabels: Record<BlockState, MessageDescriptor> = {
  filed: fmsg.stateFiled,
  open: fmsg.stateOpen,
  due_soon: fmsg.stateDueSoon,
  overdue: fmsg.stateOverdue,
};

export const kindLabels: Record<PeriodKind, MessageDescriptor> = {
  regular: fmsg.kindRegular,
  custom: fmsg.kindCustom,
  stub: fmsg.kindStub,
};
