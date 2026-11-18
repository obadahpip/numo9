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
});
