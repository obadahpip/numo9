/** Messages of the audit log screens (A-04-T09…T11). */
import { defineMessages } from "@/i18n";

export const m = defineMessages({
  title: {
    id: "audit.title",
    defaultMessage: "Audit log",
    description: "Heading of Settings → Audit log",
  },
  intro: {
    id: "audit.intro",
    defaultMessage:
      "Every change in this organisation: who made it, when, from where, and what each field was before and after. Entries can't be edited or deleted.",
    description: "Text under the audit log heading",
  },
  grid: {
    id: "audit.grid",
    defaultMessage: "Audit log events",
    description: "Accessible name of the audit log table",
  },
  filters: {
    id: "audit.filters",
    defaultMessage: "Filters",
    description: "Accessible name of the audit log filter form",
  },
  dates: { id: "audit.dates", defaultMessage: "Dates", description: "Filter: date preset" },
  from: { id: "audit.from", defaultMessage: "From", description: "Filter: first day" },
  to: { id: "audit.to", defaultMessage: "To", description: "Filter: last day" },
  user: { id: "audit.user", defaultMessage: "User", description: "Filter: who made the change" },
  everyone: {
    id: "audit.everyone",
    defaultMessage: "Everyone",
    description: "User filter option: no filter",
  },
  types: {
    id: "audit.types",
    defaultMessage: "Record types",
    description: "Filter: record types (several can be ticked)",
  },
  allTypes: {
    id: "audit.allTypes",
    defaultMessage: "All record types",
    description: "Record type filter summary when none is ticked",
  },
  someTypes: {
    id: "audit.someTypes",
    defaultMessage: "{count, plural, one {# record type} other {# record types}}",
    description: "Record type filter summary: how many are ticked",
  },
  action: { id: "audit.action", defaultMessage: "Action", description: "Filter: action" },
  anyAction: {
    id: "audit.anyAction",
    defaultMessage: "Any action",
    description: "Action filter option: no filter",
  },
  search: {
    id: "audit.search",
    defaultMessage: "Search",
    description: "Filter: text in the record, the person or the action",
  },
  searchHint: {
    id: "audit.searchHint",
    defaultMessage: "Record, person or action",
    description: "Placeholder of the audit search box",
  },
  apply: { id: "audit.apply", defaultMessage: "Show", description: "Apply the filters" },
  reset: {
    id: "audit.reset",
    defaultMessage: "Reset filters",
    description: "Back to the default filters (last 90 days, everyone)",
  },
  rangeShown: {
    id: "audit.rangeShown",
    defaultMessage: "{from} to {to} · times in {zone}",
    description: "The date range shown, e.g. 15 Aug 2026 to 12 Nov 2026 · times in America/Toronto",
  },
  batchShown: {
    id: "audit.batchShown",
    defaultMessage: "Showing one bulk operation.",
    description: "Notice when the list is filtered to one batch",
  },
  showAll: {
    id: "audit.showAll",
    defaultMessage: "Show every event",
    description: "Leaves the bulk-operation filter",
  },
  colWhen: { id: "audit.colWhen", defaultMessage: "Date and time", description: "Column" },
  colUser: { id: "audit.colUser", defaultMessage: "User", description: "Column" },
  colAction: { id: "audit.colAction", defaultMessage: "Action", description: "Column" },
  colType: { id: "audit.colType", defaultMessage: "Record type", description: "Column" },
  colRecord: { id: "audit.colRecord", defaultMessage: "Record", description: "Column" },
  colChanges: { id: "audit.colChanges", defaultMessage: "Changes", description: "Column" },
  changeCount: {
    id: "audit.changeCount",
    defaultMessage: "{count, plural, =0 {—} one {# field: {fields}} other {# fields: {fields}}}",
    description: "Changes column: how many fields changed and which",
  },
  batchCount: {
    id: "audit.batchCount",
    defaultMessage: "{count, plural, one {# change} other {# changes}}",
    description: "Changes column of a bulk operation's summary",
  },
  loadMore: {
    id: "audit.loadMore",
    defaultMessage: "Show older events",
    description: "Loads the next page of the audit log",
  },
  shown: {
    id: "audit.shown",
    defaultMessage: "{count, plural, one {# event shown} other {# events shown}}",
    description: "How many events are loaded",
  },
  allShown: {
    id: "audit.allShown",
    defaultMessage: "That's every event in this range.",
    description: "No more pages",
  },
  empty: {
    id: "audit.empty",
    defaultMessage: "No events match these filters.",
    description: "Empty audit log",
  },
  emptyHint: {
    id: "audit.emptyHint",
    defaultMessage: "Widen the dates or clear a filter.",
    description: "Next step under an empty audit log",
  },
  loading: {
    id: "audit.loading",
    defaultMessage: "Loading the audit log",
    description: "Loading state",
  },
  loadFailed: {
    id: "audit.loadFailed",
    defaultMessage: "The audit log couldn't be loaded. Refresh the page to try again.",
    description: "The audit log request failed",
  },
  notFoundTitle: {
    id: "audit.notFoundTitle",
    defaultMessage: "This organisation isn't available",
    description: "Organisation not found or not accessible",
  },
  notFoundBody: {
    id: "audit.notFoundBody",
    defaultMessage: "It doesn't exist, or you're not a member. Choose another organisation.",
    description: "Body of the not-found panel",
  },
  export: { id: "audit.export", defaultMessage: "Export", description: "Export menu button" },
  exportCsv: {
    id: "audit.exportCsv",
    defaultMessage: "CSV (every row)",
    description: "Export menu item",
  },
  exportXlsx: {
    id: "audit.exportXlsx",
    defaultMessage: "Excel (XLSX)",
    description: "Export menu item",
  },
  exportPdf: {
    id: "audit.exportPdf",
    defaultMessage: "PDF (up to 2,000 rows)",
    description: "Export menu item",
  },
  exportNote: {
    id: "audit.exportNote",
    defaultMessage: "Exports hold the same rows as this list, for the same filters.",
    description: "Text in the export menu",
  },
  // Event detail drawer
  detailTitle: {
    id: "audit.detailTitle",
    defaultMessage: "{action}: {record}",
    description: "Title of an event's detail drawer",
  },
  close: { id: "audit.close", defaultMessage: "Close", description: "Close the drawer" },
  by: { id: "audit.by", defaultMessage: "By", description: "Detail: who" },
  when: { id: "audit.when", defaultMessage: "When", description: "Detail: date and time" },
  recordType: { id: "audit.recordType", defaultMessage: "Record type", description: "Detail" },
  ip: { id: "audit.ip", defaultMessage: "IP address", description: "Detail" },
  device: { id: "audit.device", defaultMessage: "Device", description: "Detail" },
  requestId: { id: "audit.requestId", defaultMessage: "Request ID", description: "Detail" },
  eventId: { id: "audit.eventId", defaultMessage: "Event ID", description: "Detail" },
  job: { id: "audit.job", defaultMessage: "Background job", description: "Detail: the job" },
  startedBy: {
    id: "audit.startedBy",
    defaultMessage: "started by {name}",
    description: "Detail: who started the background job",
  },
  impersonated: {
    id: "audit.impersonated",
    defaultMessage: "Signed in as this person by {name} (platform support)",
    description: "Detail of an impersonation event",
  },
  openBatch: {
    id: "audit.openBatch",
    defaultMessage: "Show the {count, plural, one {# change} other {# changes}} of this operation",
    description: "Filters the list to one bulk operation",
  },
  noChanges: {
    id: "audit.noChanges",
    defaultMessage: "No field values were recorded for this event.",
    description: "Event without a diff",
  },
  // DiffViewer
  diff: {
    id: "audit.diff",
    defaultMessage: "What changed",
    description: "Accessible name of the list of changed fields",
  },
  before: { id: "audit.before", defaultMessage: "Before", description: "Old value label" },
  after: { id: "audit.after", defaultMessage: "After", description: "New value label" },
  empty_value: {
    id: "audit.emptyValue",
    defaultMessage: "(empty)",
    description: "A value that was or became empty",
  },
  hidden: {
    id: "audit.hidden",
    defaultMessage: "Hidden",
    description: "A masked value (SIN, bank details)",
  },
  hiddenNote: {
    id: "audit.hiddenNote",
    defaultMessage: "Changed — the value is hidden for privacy",
    description: "A masked field that changed",
  },
  truncated: {
    id: "audit.truncated",
    defaultMessage: "{text}… ({length} characters)",
    description: "A long value cut in the list",
  },
  none: { id: "audit.none", defaultMessage: "—", description: "No value (dash)" },
  yes: { id: "audit.yes", defaultMessage: "Yes", description: "A true value" },
  no: { id: "audit.no", defaultMessage: "No", description: "A false value" },
  // DataGrid labels
  gridSearch: {
    id: "audit.gridSearch",
    defaultMessage: "Search the events shown",
    description: "DataGrid search box (searches the loaded rows)",
  },
  gridColumns: { id: "audit.gridColumns", defaultMessage: "Columns", description: "Grid" },
  gridDensity: { id: "audit.gridDensity", defaultMessage: "Row height", description: "Grid" },
  gridComfortable: {
    id: "audit.gridComfortable",
    defaultMessage: "Comfortable",
    description: "Grid density",
  },
  gridCompact: { id: "audit.gridCompact", defaultMessage: "Compact", description: "Grid" },
  gridAll: { id: "audit.gridAll", defaultMessage: "All", description: "Grid filter option" },
  gridChip: {
    id: "audit.gridChip",
    defaultMessage: "{column}: {value}",
    description: "Grid filter chip",
  },
  gridClear: { id: "audit.gridClear", defaultMessage: "Clear", description: "Grid" },
  gridSelectAll: { id: "audit.gridSelectAll", defaultMessage: "Select all", description: "Grid" },
  gridSelectRow: {
    id: "audit.gridSelectRow",
    defaultMessage: "Select {row}",
    description: "Grid",
  },
  gridSelected: {
    id: "audit.gridSelected",
    defaultMessage: "{count} selected",
    description: "Grid",
  },
  gridClearSelection: {
    id: "audit.gridClearSelection",
    defaultMessage: "Clear selection",
    description: "Grid",
  },
  gridResults: {
    id: "audit.gridResults",
    defaultMessage: "{shown} of {total} events",
    description: "Grid live region after searching",
  },
  // Date picker
  openCalendar: {
    id: "audit.openCalendar",
    defaultMessage: "Open calendar",
    description: "Date picker button",
  },
  previousMonth: {
    id: "audit.previousMonth",
    defaultMessage: "Previous month",
    description: "Calendar",
  },
  nextMonth: { id: "audit.nextMonth", defaultMessage: "Next month", description: "Calendar" },
  unreadable: {
    id: "audit.unreadable",
    defaultMessage: "Enter a date, e.g. 26 Oct 2026",
    description: "Typed text isn't a date",
  },
  // Record history drawer (A-04-T10)
  history: {
    id: "audit.history",
    defaultMessage: "History",
    description: "Button that opens a record's history",
  },
  historyOf: {
    id: "audit.historyOf",
    defaultMessage: "History of {record}",
    description: "Title of the record history drawer",
  },
  historyLoading: {
    id: "audit.historyLoading",
    defaultMessage: "Loading the history",
    description: "Loading state of the record history drawer",
  },
  historyEmpty: {
    id: "audit.historyEmpty",
    defaultMessage: "No changes recorded for this record yet.",
    description: "Record without history",
  },
  historyFailed: {
    id: "audit.historyFailed",
    defaultMessage: "The history couldn't be loaded. Close and open it again.",
    description: "History request failed",
  },
  historyMore: {
    id: "audit.historyMore",
    defaultMessage: "Show older changes",
    description: "Next page of a record's history",
  },
  timeline: {
    id: "audit.timeline",
    defaultMessage: "Changes, newest first",
    description: "Accessible name of the history timeline",
  },
  asOf: {
    id: "audit.asOf",
    defaultMessage: "View as of",
    description: "Date field: show the record as it was at the end of that day",
  },
  asOfShow: {
    id: "audit.asOfShow",
    defaultMessage: "Show",
    description: "Button: rebuild the record as of the chosen date",
  },
  asOfTitle: {
    id: "audit.asOfTitle",
    defaultMessage: "{record} at the end of {date}",
    description: "Heading of the record rebuilt as of a date",
  },
  asOfMissing: {
    id: "audit.asOfMissing",
    defaultMessage: "This record didn't exist yet on that date.",
    description: "As-of date before the record was created",
  },
  asOfDeleted: {
    id: "audit.asOfDeleted",
    defaultMessage: "This record was deleted on that date. Its last values:",
    description: "As-of date while the record was deleted",
  },
  asOfPartial: {
    id: "audit.asOfPartial",
    defaultMessage:
      "This record's history starts after it was created, so only the fields changed since are shown.",
    description: "History does not start at creation",
  },
  asOfFailed: {
    id: "audit.asOfFailed",
    defaultMessage: "The record couldn't be rebuilt for that date. Choose the date again.",
    description: "As-of request failed",
  },
  asOfFields: {
    id: "audit.asOfFields",
    defaultMessage: "Fields as they were",
    description: "Accessible name of the rebuilt fields",
  },
  openLog: {
    id: "audit.openLog",
    defaultMessage: "Open in the audit log",
    description: "Link from the history drawer to the full audit log filtered to the record",
  },
});

export const presetLabels = defineMessages({
  today: { id: "audit.preset.today", defaultMessage: "Today", description: "Date preset" },
  last7: { id: "audit.preset.last7", defaultMessage: "Last 7 days", description: "Date preset" },
  last30: { id: "audit.preset.last30", defaultMessage: "Last 30 days", description: "Date preset" },
  last90: { id: "audit.preset.last90", defaultMessage: "Last 90 days", description: "Date preset" },
  thisMonth: {
    id: "audit.preset.thisMonth",
    defaultMessage: "This month",
    description: "Date preset",
  },
  thisQuarter: {
    id: "audit.preset.thisQuarter",
    defaultMessage: "This quarter",
    description: "Date preset",
  },
  thisFiscalYear: {
    id: "audit.preset.thisFiscalYear",
    defaultMessage: "This fiscal year",
    description: "Date preset",
  },
  custom: {
    id: "audit.preset.custom",
    defaultMessage: "Custom dates",
    description: "Date preset: choose From and To",
  },
});
