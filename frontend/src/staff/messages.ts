import { defineMessages } from "@/i18n";

/** Practice staff screens (V-05). */
export const m = defineMessages({
  breadcrumb: { id: "staff.breadcrumb", defaultMessage: "Staff", description: "Breadcrumb" },
  assignmentsTitle: {
    id: "staff.assignments.title",
    defaultMessage: "{name} works on",
    description: "Assignment editor heading",
  },
  organisations: {
    id: "staff.assignments.organisations",
    defaultMessage: "Organisations (direct)",
    description: "Section",
  },
  groups: {
    id: "staff.assignments.groups",
    defaultMessage: "Groups (every organisation in them)",
    description: "Section",
  },
  none: { id: "staff.assignments.none", defaultMessage: "None yet.", description: "Empty list" },
  searchOrganisations: {
    id: "staff.assignments.searchOrganisations",
    defaultMessage: "Add an organisation",
    description: "Search field",
  },
  add: { id: "staff.assignments.add", defaultMessage: "Add {name}", description: "Search result" },
  remove: {
    id: "staff.assignments.remove",
    defaultMessage: "Remove {name}",
    description: "Remove an assignment",
  },
  group: { id: "staff.assignments.group", defaultMessage: "Group", description: "Field" },
  role: { id: "staff.assignments.role", defaultMessage: "Role in the group", description: "Field" },
  addGroup: {
    id: "staff.assignments.addGroup",
    defaultMessage: "Assign to group",
    description: "Button",
  },
  choose: {
    id: "staff.assignments.choose",
    defaultMessage: "Choose…",
    description: "Empty option",
  },
  roleAccountant: {
    id: "staff.role.accountant",
    defaultMessage: "Accountant",
    description: "Role",
  },
  roleReviewer: { id: "staff.role.reviewer", defaultMessage: "Reviewer", description: "Role" },
  rolePayroll: {
    id: "staff.role.payroll",
    defaultMessage: "Payroll specialist",
    description: "Role",
  },
  roleReadOnly: { id: "staff.role.readOnly", defaultMessage: "Read only", description: "Role" },
  immediate: {
    id: "staff.assignments.immediate",
    defaultMessage: "Changes apply at once: the next page they open already sees them.",
    description: "Hint",
  },
  saved: { id: "staff.assignments.saved", defaultMessage: "Saved", description: "Status" },
  failed: {
    id: "staff.assignments.failed",
    defaultMessage: "We couldn't save the change. Try again.",
    description: "Error",
  },
  loadFailed: {
    id: "staff.loadFailed",
    defaultMessage: "We couldn't load this staff member",
    description: "Error",
  },
  retry: { id: "staff.retry", defaultMessage: "Try again", description: "Retry" },
  dormantTitle: {
    id: "staff.dormant.title",
    defaultMessage: "Dormant staff",
    description: "Dashboard widget heading",
  },
  dormantIntro: {
    id: "staff.dormant.intro",
    defaultMessage: "No sign-in for {days} days or more, but they can still open your clients.",
    description: "Dashboard widget explanation",
  },
  dormantLine: {
    id: "staff.dormant.line",
    defaultMessage: "{name} — {days, plural, one {# day} other {# days}} without signing in",
    description: "A dormant staff member",
  },
  suspend: {
    id: "staff.dormant.suspend",
    defaultMessage: "Suspend access for {name}",
    description: "One-click suspend",
  },
  suspended: {
    id: "staff.dormant.suspended",
    defaultMessage: "{name}'s access is suspended.",
    description: "After suspending",
  },
  activityTitle: {
    id: "staff.activity.title",
    defaultMessage: "Activity — last 12 months",
    description: "Heatmap heading",
  },
  activityChart: {
    id: "staff.activity.chart",
    defaultMessage:
      "Activity, last 12 months: {total, plural, one {# change} other {# changes}} in the audit log",
    description: "Accessible name of the heatmap",
  },
  activityDay: {
    id: "staff.activity.day",
    defaultMessage: "{count, plural, =0 {No changes} one {# change} other {# changes}} on {date}",
    description: "Heatmap tooltip of one day",
  },
  activityLess: { id: "staff.activity.less", defaultMessage: "Less", description: "Legend" },
  activityMore: { id: "staff.activity.more", defaultMessage: "More", description: "Legend" },
  activityTable: {
    id: "staff.activity.showTable",
    defaultMessage: "Show as a table",
    description: "Heatmap toggle",
  },
  activityChartToggle: {
    id: "staff.activity.showChart",
    defaultMessage: "Show as a chart",
    description: "Heatmap toggle",
  },
  activityDate: { id: "staff.activity.date", defaultMessage: "Day", description: "Table column" },
  activityCount: {
    id: "staff.activity.count",
    defaultMessage: "Changes",
    description: "Table column",
  },
  activityEmpty: {
    id: "staff.activity.empty",
    defaultMessage: "No activity in the last 12 months.",
    description: "Empty table",
  },
  groupLine: {
    id: "staff.assignments.groupLine",
    defaultMessage: "{name} · {role}",
    description: "A group assignment: group and role",
  },
  personLine: {
    id: "staff.personLine",
    defaultMessage: "{role} · {email}",
    description: "Under a staff member's name",
  },
  listTitle: { id: "staff.list.title", defaultMessage: "Staff", description: "Page heading" },
  listIntro: {
    id: "staff.list.intro",
    defaultMessage:
      "Everyone in your practice, the organisations they can open and when they last signed in.",
    description: "Under the heading",
  },
  grid: { id: "staff.list.grid", defaultMessage: "Staff", description: "Grid name" },
  gridSearch: { id: "staff.list.search", defaultMessage: "Search", description: "Grid search" },
  gridColumns: { id: "staff.list.columns", defaultMessage: "Columns", description: "Grid" },
  gridDensity: { id: "staff.list.density", defaultMessage: "Density", description: "Grid" },
  gridComfortable: {
    id: "staff.list.comfortable",
    defaultMessage: "Comfortable",
    description: "Grid density",
  },
  gridCompact: { id: "staff.list.compact", defaultMessage: "Compact", description: "Density" },
  gridAll: { id: "staff.list.all", defaultMessage: "All", description: "Filter: any value" },
  gridChip: {
    id: "staff.list.chip",
    defaultMessage: "{column}: {value}",
    description: "Filter chip",
  },
  gridClear: { id: "staff.list.clear", defaultMessage: "Clear filters", description: "Grid" },
  gridSelectAll: { id: "staff.list.selectAll", defaultMessage: "Select all", description: "Grid" },
  gridSelectRow: {
    id: "staff.list.selectRow",
    defaultMessage: "Select {row}",
    description: "Row checkbox",
  },
  gridSelected: {
    id: "staff.list.selected",
    defaultMessage: "{count} selected",
    description: "Bulk bar",
  },
  gridClearSelection: {
    id: "staff.list.clearSelection",
    defaultMessage: "Clear selection",
    description: "Bulk bar",
  },
  gridResults: {
    id: "staff.list.results",
    defaultMessage: "{shown, plural, one {# person} other {# people}} of {total}",
    description: "Live region after filtering",
  },
  loading: { id: "staff.list.loading", defaultMessage: "Loading staff…", description: "Loading" },
  colName: { id: "staff.list.colName", defaultMessage: "Name", description: "Column" },
  colRole: { id: "staff.list.colRole", defaultMessage: "Practice role", description: "Column" },
  colOrganisations: {
    id: "staff.list.colOrganisations",
    defaultMessage: "Organisations",
    description: "Column: organisations they can open",
  },
  colLastActive: {
    id: "staff.list.colLastActive",
    defaultMessage: "Last active",
    description: "Column: last sign-in",
  },
  colStatus: { id: "staff.list.colStatus", defaultMessage: "Status", description: "Column" },
  never: { id: "staff.list.never", defaultMessage: "Never signed in", description: "Last active" },
  statusActive: { id: "staff.status.active", defaultMessage: "Active", description: "Status" },
  statusDormant: { id: "staff.status.dormant", defaultMessage: "Dormant", description: "Status" },
  statusSuspended: {
    id: "staff.status.suspended",
    defaultMessage: "Suspended",
    description: "Status",
  },
  statusPending: {
    id: "staff.status.pending",
    defaultMessage: "Invitation pending",
    description: "Status",
  },
  expires: {
    id: "staff.list.expires",
    defaultMessage: "Expires {date}",
    description: "Pending invitation expiry",
  },
  empty: {
    id: "staff.list.empty",
    defaultMessage: "Nobody here yet",
    description: "Empty staff list",
  },
  emptyBody: {
    id: "staff.list.emptyBody",
    defaultMessage: "Invite accountants from the practice settings to see them here.",
    description: "Empty staff list",
  },
  noResults: {
    id: "staff.list.noResults",
    defaultMessage: "Nobody matches your search",
    description: "No results",
  },
  listFailed: {
    id: "staff.list.failed",
    defaultMessage: "We couldn't load your staff",
    description: "Error",
  },
  statusLine: {
    id: "staff.member.statusLine",
    defaultMessage: "Status",
    description: "Label of the status badge on a staff member's page",
  },
  suspendAction: {
    id: "staff.member.suspend",
    defaultMessage: "Suspend access",
    description: "Button",
  },
  reinstateAction: {
    id: "staff.member.reinstate",
    defaultMessage: "Lift suspension",
    description: "Button",
  },
  removeAction: {
    id: "staff.member.remove",
    defaultMessage: "Remove from practice",
    description: "Button",
  },
  removeTitle: {
    id: "staff.member.removeTitle",
    defaultMessage: "Remove {name} from the practice?",
    description: "Confirmation dialog title",
  },
  removeBody: {
    id: "staff.member.removeBody",
    defaultMessage:
      "They lose access to every organisation at once. Their history in the audit log stays.",
    description: "Confirmation dialog",
  },
  cancel: { id: "staff.member.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "staff.member.close", defaultMessage: "Close", description: "Dialog × button" },
  reinstated: {
    id: "staff.member.reinstated",
    defaultMessage: "{name} can sign in to your clients again.",
    description: "After lifting the suspension",
  },
  actionFailed: {
    id: "staff.member.actionFailed",
    defaultMessage: "We couldn't make the change. Try again.",
    description: "Error without an explanation from the server",
  },
  backToStaff: {
    id: "staff.member.back",
    defaultMessage: "All staff",
    description: "Link back to the list",
  },
});
