import { defineMessages } from "@/i18n";

/** Console → Feature flags (U-06-T12). */
export const m = defineMessages({
  title: { id: "console.flags.title", defaultMessage: "Feature flags", description: "Heading" },
  crumb: {
    id: "console.flags.crumb",
    defaultMessage: "Platform console · Feature flags",
    description: "Breadcrumb",
  },
  intro: {
    id: "console.flags.intro",
    defaultMessage:
      "Turn a flag on or off for everyone, or by rule: chosen organisations and practices, and a stable percentage of organisations. Changes apply on the next page load.",
    description: "Under the heading",
  },
  newFlag: { id: "console.flags.newFlag", defaultMessage: "New flag", description: "Form heading" },
  name: { id: "console.flags.name", defaultMessage: "Name", description: "Field" },
  nameHint: {
    id: "console.flags.nameHint",
    defaultMessage: "Lower-case, for example payroll.new_t4_screen",
    description: "Field hint",
  },
  note: { id: "console.flags.note", defaultMessage: "Note", description: "Field" },
  create: { id: "console.flags.create", defaultMessage: "Create flag", description: "Button" },
  empty: {
    id: "console.flags.empty",
    defaultMessage: "No feature flags yet. Create the first one above.",
    description: "Empty list",
  },
  mode: { id: "console.flags.mode", defaultMessage: "Who sees it", description: "Group label" },
  on: { id: "console.flags.on", defaultMessage: "On for everyone", description: "Mode" },
  off: { id: "console.flags.off", defaultMessage: "Off for everyone", description: "Mode" },
  rules: { id: "console.flags.rules", defaultMessage: "By rule", description: "Mode" },
  percent: {
    id: "console.flags.percent",
    defaultMessage: "Percentage of organisations",
    description: "Field",
  },
  savePercent: {
    id: "console.flags.savePercent",
    defaultMessage: "Save percentage",
    description: "Button",
  },
  organisations: {
    id: "console.flags.organisations",
    defaultMessage: "Organisations",
    description: "Rule list",
  },
  practices: {
    id: "console.flags.practices",
    defaultMessage: "Practices",
    description: "Rule list",
  },
  none: { id: "console.flags.none", defaultMessage: "None", description: "Empty rule list" },
  remove: {
    id: "console.flags.remove",
    defaultMessage: "Remove {name}",
    description: "Remove a target from a flag",
  },
  addOrganisation: {
    id: "console.flags.addOrganisation",
    defaultMessage: "Add an organisation",
    description: "Search field",
  },
  addPractice: {
    id: "console.flags.addPractice",
    defaultMessage: "Add a practice",
    description: "Search field",
  },
  add: { id: "console.flags.add", defaultMessage: "Add {name}", description: "Search result" },
  delete: { id: "console.flags.delete", defaultMessage: "Delete flag", description: "Button" },
  deleteTitle: {
    id: "console.flags.deleteTitle",
    defaultMessage: "Delete {name}?",
    description: "Confirm dialog title",
  },
  deleteBody: {
    id: "console.flags.deleteBody",
    defaultMessage:
      "Code that still asks for this flag will see it off. This can't be undone, but you can create it again.",
    description: "Confirm dialog body",
  },
  cancel: { id: "console.flags.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "console.flags.close", defaultMessage: "Close", description: "Button" },
  saved: { id: "console.flags.saved", defaultMessage: "{name} saved", description: "Status" },
  failed: {
    id: "console.flags.failed",
    defaultMessage: "We couldn't save the change. Try again.",
    description: "Error",
  },
  loadFailed: {
    id: "console.flags.loadFailed",
    defaultMessage: "We couldn't load the feature flags",
    description: "Error",
  },
  retry: { id: "console.flags.retry", defaultMessage: "Try again", description: "Retry" },
});
