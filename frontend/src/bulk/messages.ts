import { defineMessages } from "@/i18n";

/** Bulk actions in the directory (V-03-T08…T10). */
export const m = defineMessages({
  selectedPage: {
    id: "bulk.selectedPage",
    defaultMessage: "{count, plural, one {# selected} other {# selected}}",
    description: "Selection bar: ticked rows",
  },
  selectAll: {
    id: "bulk.selectAll",
    defaultMessage:
      "{count, plural, one {Select the # organisation matching} other {Select all # matching}}",
    description: "Selection bar: extend to every organisation matching the search and filters",
  },
  allSelected: {
    id: "bulk.allSelected",
    defaultMessage:
      "{count, plural, one {The # organisation matching is selected} other {All # organisations matching are selected}}",
    description: "Selection bar when all matching are selected",
  },
  clear: { id: "bulk.clear", defaultMessage: "Clear selection", description: "Selection bar" },
  actions: { id: "bulk.actions", defaultMessage: "Bulk actions", description: "Group label" },
  group: { id: "bulk.action.group", defaultMessage: "Move to group", description: "Bulk action" },
  tags: { id: "bulk.action.tags", defaultMessage: "Tags", description: "Bulk action" },
  staff: { id: "bulk.action.staff", defaultMessage: "Assign staff", description: "Bulk action" },
  settings: { id: "bulk.action.settings", defaultMessage: "Settings", description: "Bulk action" },
  message: { id: "bulk.action.message", defaultMessage: "Message", description: "Bulk action" },
  export: { id: "bulk.action.export", defaultMessage: "Export", description: "Bulk action" },

  dialogTitle: {
    id: "bulk.dialogTitle",
    defaultMessage: "{action} — {count, plural, one {# organisation} other {# organisations}}",
    description: "Bulk dialog title",
  },
  close: { id: "bulk.close", defaultMessage: "Close", description: "Button" },
  cancel: { id: "bulk.cancel", defaultMessage: "Cancel", description: "Button" },
  previewButton: {
    id: "bulk.previewButton",
    defaultMessage: "Preview changes",
    description: "Form → preview",
  },
  back: { id: "bulk.back", defaultMessage: "Back", description: "Preview → form" },
  apply: {
    id: "bulk.apply",
    defaultMessage:
      "{count, plural, one {Apply to # organisation} other {Apply to # organisations}}",
    description: "Preview → start the job",
  },
  nothingYet: {
    id: "bulk.nothingYet",
    defaultMessage: "Nothing has changed yet. Review the changes, then apply.",
    description: "Preview explanation",
  },
  willChange: {
    id: "bulk.willChange",
    defaultMessage: "{count, plural, one {# will change} other {# will change}}",
    description: "Preview count",
  },
  noChange: {
    id: "bulk.noChange",
    defaultMessage: "{count, plural, one {# no change} other {# no change}}",
    description: "Preview count",
  },
  skipped: {
    id: "bulk.skipped",
    defaultMessage: "{count, plural, one {# skipped} other {# skipped}}",
    description: "Preview count",
  },
  showing: {
    id: "bulk.showing",
    defaultMessage: "Showing {shown} of {total}. The full list is in the results after applying.",
    description: "Under the preview table",
  },
  colOrganisation: {
    id: "bulk.col.organisation",
    defaultMessage: "Organisation",
    description: "Column",
  },
  colChange: { id: "bulk.col.change", defaultMessage: "Change", description: "Column" },
  colCurrent: { id: "bulk.col.current", defaultMessage: "Current", description: "Column" },
  colNew: { id: "bulk.col.new", defaultMessage: "New", description: "Column" },
  statusChange: { id: "bulk.status.change", defaultMessage: "Will change", description: "Line" },
  statusNoChange: { id: "bulk.status.noChange", defaultMessage: "No change", description: "Line" },
  statusSkipped: { id: "bulk.status.skipped", defaultMessage: "Skipped", description: "Line" },
  failed: {
    id: "bulk.failed",
    defaultMessage: "We couldn't prepare the bulk action. Try again.",
    description: "Error",
  },
  groupField: { id: "bulk.field.group", defaultMessage: "Group", description: "Field" },
  mode: { id: "bulk.field.mode", defaultMessage: "How", description: "Field" },
  modeMove: {
    id: "bulk.mode.move",
    defaultMessage: "Move (leave other groups)",
    description: "Group mode",
  },
  modeAdd: {
    id: "bulk.mode.add",
    defaultMessage: "Add (keep other groups)",
    description: "Group mode",
  },
  modeRemove: {
    id: "bulk.mode.remove",
    defaultMessage: "Remove from the group",
    description: "Group mode",
  },
  choose: { id: "bulk.choose", defaultMessage: "Choose…", description: "Empty select option" },
  addTags: { id: "bulk.field.addTags", defaultMessage: "Add these tags", description: "Field" },
  removeTags: {
    id: "bulk.field.removeTags",
    defaultMessage: "Remove these tags",
    description: "Field",
  },
  noTags: {
    id: "bulk.noTags",
    defaultMessage: "The practice has no tags yet.",
    description: "Empty",
  },
  member: { id: "bulk.field.member", defaultMessage: "Staff member", description: "Field" },
  assign: { id: "bulk.mode.assign", defaultMessage: "Assign", description: "Staff mode" },
  unassign: { id: "bulk.mode.unassign", defaultMessage: "Unassign", description: "Staff mode" },
  setting: { id: "bulk.field.setting", defaultMessage: "Setting", description: "Field" },
  salesTerms: {
    id: "bulk.setting.salesTerms",
    defaultMessage: "Default sales terms",
    description: "Setting",
  },
  purchaseTerms: {
    id: "bulk.setting.purchaseTerms",
    defaultMessage: "Default purchase terms",
    description: "Setting",
  },
  timeFormat: {
    id: "bulk.setting.timeFormat",
    defaultMessage: "Time format",
    description: "Setting",
  },
  fiscalYearEnd: {
    id: "bulk.setting.fiscalYearEnd",
    defaultMessage: "Fiscal year end (only organisations without posted transactions)",
    description: "Setting",
  },
  termsType: { id: "bulk.field.termsType", defaultMessage: "Due date", description: "Field" },
  daysAfterDocument: {
    id: "bulk.terms.daysAfterDocument",
    defaultMessage: "days after the document date",
    description: "Terms type",
  },
  daysAfterMonthEnd: {
    id: "bulk.terms.daysAfterMonthEnd",
    defaultMessage: "days after the end of the document month",
    description: "Terms type",
  },
  dayOfFollowingMonth: {
    id: "bulk.terms.dayOfFollowingMonth",
    defaultMessage: "of the following month",
    description: "Terms type",
  },
  dayOfCurrentMonth: {
    id: "bulk.terms.dayOfCurrentMonth",
    defaultMessage: "of the current month",
    description: "Terms type",
  },
  days: { id: "bulk.field.days", defaultMessage: "Days or day", description: "Field" },
  h12: { id: "bulk.time.h12", defaultMessage: "12-hour (2:30 PM)", description: "Time format" },
  h24: { id: "bulk.time.h24", defaultMessage: "24-hour (14:30)", description: "Time format" },
  month: { id: "bulk.field.month", defaultMessage: "Month (1–12)", description: "Field" },
  day: { id: "bulk.field.day", defaultMessage: "Day", description: "Field" },
  subject: { id: "bulk.field.subject", defaultMessage: "Subject", description: "Field" },
  body: { id: "bulk.field.body", defaultMessage: "Message", description: "Field" },
  messageHint: {
    id: "bulk.messageHint",
    defaultMessage: "Sent to each organisation's owners and admins, in the app and by email.",
    description: "Message hint",
  },
  format: { id: "bulk.field.format", defaultMessage: "File", description: "Field" },
  csv: { id: "bulk.format.csv", defaultMessage: "CSV", description: "Format" },
  xlsx: { id: "bulk.format.xlsx", defaultMessage: "Excel (XLSX)", description: "Format" },
});
