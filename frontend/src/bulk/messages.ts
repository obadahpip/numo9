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
});
