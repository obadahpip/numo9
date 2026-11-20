import { defineMessages } from "@/i18n";

export const m = defineMessages({
  crumb: {
    id: "dashboard.crumb",
    defaultMessage: "Dashboard",
    description: "Breadcrumb of the practice home (V-04)",
  },
  title: { id: "dashboard.title", defaultMessage: "Practice home", description: "Page heading" },
  intro: {
    id: "dashboard.intro",
    defaultMessage:
      "Every number opens the directory with the same filter — the list shows exactly that many organisations.",
    description: "Text under the heading",
  },
  scope: {
    id: "dashboard.scope",
    defaultMessage: "Show",
    description: "Label of the my organisations / all practice switch",
  },
  scopeMine: {
    id: "dashboard.scopeMine",
    defaultMessage: "My organisations",
    description: "Scope option",
  },
  scopeAll: {
    id: "dashboard.scopeAll",
    defaultMessage: "All practice",
    description: "Scope option",
  },
  openDirectory: {
    id: "dashboard.openDirectory",
    defaultMessage: "Open in directory",
    description: "Card link to the pre-filtered directory",
  },
  openDirectoryLabel: {
    id: "dashboard.openDirectoryLabel",
    defaultMessage: "Open in directory: {title}",
    description: "Accessible name of a card link",
  },
  openStaff: {
    id: "dashboard.openStaff",
    defaultMessage: "Open staff",
    description: "Card link to the staff list",
  },
  openStaffLabel: {
    id: "dashboard.openStaffLabel",
    defaultMessage: "Open staff: {title}",
    description: "Accessible name of a card link",
  },
  widgetFailed: {
    id: "dashboard.widgetFailed",
    defaultMessage: "Couldn't load this figure.",
    description: "One card's error (the rest of the page still loads)",
  },
  retry: { id: "dashboard.retry", defaultMessage: "Try again", description: "Button" },
  retryLabel: {
    id: "dashboard.retryLabel",
    defaultMessage: "Try again: {title}",
    description: "Accessible name of a card's retry button",
  },
  loadFailed: {
    id: "dashboard.loadFailed",
    defaultMessage: "The practice home didn't load",
    description: "Whole-page error",
  },
  loadFailedBody: {
    id: "dashboard.loadFailedBody",
    defaultMessage: "Your connection may have dropped: try again. The directory still works.",
    description: "Whole-page error text",
  },
  loading: {
    id: "dashboard.loading",
    defaultMessage: "Loading the dashboard…",
    description: "Busy",
  },
  deadlinesEmpty: {
    id: "dashboard.deadlinesEmpty",
    defaultMessage: "No deadline in the next 30 days.",
    description: "Empty deadlines list",
  },
  workloadLine: {
    id: "dashboard.workloadLine",
    defaultMessage:
      "{organisations, plural, one {# organisation} other {# organisations}} · {tasks, plural, one {# open task} other {# open tasks}}",
    description: "One staff member's workload",
  },
  workloadEmpty: {
    id: "dashboard.workloadEmpty",
    defaultMessage: "No active staff member.",
    description: "Empty workload",
  },
  customise: {
    id: "dashboard.customise",
    defaultMessage: "Customise dashboard",
    description: "Button: reorder and hide cards (V-04-T09)",
  },
  customiseTitle: {
    id: "dashboard.customiseTitle",
    defaultMessage: "Customise your dashboard",
    description: "Heading of the customise panel",
  },
  customiseIntro: {
    id: "dashboard.customiseIntro",
    defaultMessage:
      "Move cards up or down and choose which ones you see. Only your dashboard changes.",
    description: "Text of the customise panel",
  },
  show: {
    id: "dashboard.show",
    defaultMessage: "Show {title}",
    description: "Checkbox: show this card",
  },
  moveUp: { id: "dashboard.moveUp", defaultMessage: "Move up: {title}", description: "Button" },
  moveDown: {
    id: "dashboard.moveDown",
    defaultMessage: "Move down: {title}",
    description: "Button",
  },
  up: { id: "dashboard.up", defaultMessage: "Up", description: "Button text" },
  down: { id: "dashboard.down", defaultMessage: "Down", description: "Button text" },
  save: { id: "dashboard.save", defaultMessage: "Save layout", description: "Button" },
  cancel: { id: "dashboard.cancel", defaultMessage: "Cancel", description: "Button" },
  saved: {
    id: "dashboard.saved",
    defaultMessage: "Your dashboard layout is saved.",
    description: "Status after saving",
  },
  saveFailed: {
    id: "dashboard.saveFailed",
    defaultMessage: "The layout wasn't saved. Try again.",
    description: "Error",
  },
});
