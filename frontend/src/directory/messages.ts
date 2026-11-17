import { defineMessages } from "@/i18n";

/** Organisation directory (V-01): page, grid, filters, saved views, go to organisation. */
export const m = defineMessages({
  title: {
    id: "directory.title",
    defaultMessage: "Organisations",
    description: "Heading of the practice's organisation directory",
  },
  breadcrumb: {
    id: "directory.breadcrumb",
    defaultMessage: "Directory",
    description: "Breadcrumb and navigation name of the practice's organisation directory",
  },
  summary: {
    id: "directory.summary",
    defaultMessage:
      "{total, plural, one {# organisation} other {# organisations}} assigned to {practice}",
    description: "Line under the heading: how many organisations the user sees in the practice",
  },
  summaryFiltered: {
    id: "directory.summaryFiltered",
    defaultMessage:
      "{count, number} of {total, plural, one {# organisation} other {# organisations}}",
    description: "Line under the heading while a search or filter is on",
  },
  viewChanged: {
    id: "directory.viewChanged",
    defaultMessage: "View “{name}” (changed)",
    description: "Under the heading: the open saved view has unsaved changes",
  },
  viewOpen: {
    id: "directory.viewOpen",
    defaultMessage: "View “{name}”",
    description: "Under the heading: the saved view that is open",
  },
  newOrganisation: {
    id: "directory.newOrganisation",
    defaultMessage: "New organisation",
    description: "Button: create a client organisation",
  },
  searchPlaceholder: {
    id: "directory.searchPlaceholder",
    defaultMessage: "Search name, BN, owner, tag… (/)",
    description: "Placeholder of the directory search box; / is the shortcut that focuses it",
  },
  // ---- grid
  gridName: {
    id: "directory.grid.name",
    defaultMessage: "Organisations",
    description: "Accessible name of the grid",
  },
  gridSearch: {
    id: "directory.grid.search",
    defaultMessage: "Search organisations",
    description: "Accessible name of the search box",
  },
  gridColumns: {
    id: "directory.grid.columns",
    defaultMessage: "Columns",
    description: "Column chooser button",
  },
  gridDensity: {
    id: "directory.grid.density",
    defaultMessage: "Row height",
    description: "Density toggle group",
  },
  gridComfortable: {
    id: "directory.grid.comfortable",
    defaultMessage: "Comfortable",
    description: "Density option",
  },
  gridCompact: {
    id: "directory.grid.compact",
    defaultMessage: "Compact",
    description: "Density option",
  },
  gridAll: {
    id: "directory.grid.all",
    defaultMessage: "All",
    description: "Filter chip: any value",
  },
  gridChip: {
    id: "directory.grid.chip",
    defaultMessage: "{column}: {value}",
    description: "Filter chip text",
  },
  gridClear: {
    id: "directory.grid.clear",
    defaultMessage: "Clear search and filters",
    description: "Button",
  },
  gridSelectAll: {
    id: "directory.grid.selectAll",
    defaultMessage: "Select all organisations shown",
    description: "Header checkbox",
  },
  gridSelectRow: {
    id: "directory.grid.selectRow",
    defaultMessage: "Select {row}",
    description: "Row checkbox",
  },
  gridSelected: {
    id: "directory.grid.selected",
    defaultMessage: "{count, number} selected",
    description: "Bulk bar count",
  },
  gridClearSelection: {
    id: "directory.grid.clearSelection",
    defaultMessage: "Clear selection",
    description: "Bulk bar button",
  },
  gridResults: {
    id: "directory.grid.results",
    defaultMessage:
      "{shown, number} of {total, plural, one {# organisation} other {# organisations}}",
    description: "Announced after a search or filter",
  },
  gridReorder: {
    id: "directory.grid.reorder",
    defaultMessage: "Drag to reorder, or press Alt+↑ / Alt+↓.",
    description: "Hint at the bottom of the column chooser",
  },
  gridMoved: {
    id: "directory.grid.moved",
    defaultMessage: "{column} moved to position {position, number} of {total, number}",
    description: "Announced after a column was moved in the column chooser",
  },
  loading: {
    id: "directory.loading",
    defaultMessage: "Loading organisations",
    description: "Announced while loading",
  },
  // ---- columns
  colName: { id: "directory.col.name", defaultMessage: "Organisation", description: "Column" },
  colLegalName: {
    id: "directory.col.legalName",
    defaultMessage: "Legal name",
    description: "Column",
  },
  colBn: { id: "directory.col.bn", defaultMessage: "BN", description: "Column: Business Number" },
  colOwner: { id: "directory.col.owner", defaultMessage: "Owner", description: "Column" },
  colIndustry: { id: "directory.col.industry", defaultMessage: "Industry", description: "Column" },
  colProvince: { id: "directory.col.province", defaultMessage: "Province", description: "Column" },
  colPackage: { id: "directory.col.package", defaultMessage: "Package", description: "Column" },
  colStatus: { id: "directory.col.status", defaultMessage: "Status", description: "Column" },
  colFye: {
    id: "directory.col.fye",
    defaultMessage: "FYE",
    description: "Column: fiscal year end",
  },
  colGstCycle: {
    id: "directory.col.gstCycle",
    defaultMessage: "GST/HST cycle",
    description: "Column",
  },
  colPayroll: { id: "directory.col.payroll", defaultMessage: "Payroll", description: "Column" },
  colOverdue: {
    id: "directory.col.overdue",
    defaultMessage: "Overdue",
    description: "Column: overdue items",
  },
  colUnfiled: {
    id: "directory.col.unfiled",
    defaultMessage: "Unfiled",
    description: "Column: unfiled returns",
  },
  colTags: { id: "directory.col.tags", defaultMessage: "Tags", description: "Column" },
  colGroups: { id: "directory.col.groups", defaultMessage: "Groups", description: "Column" },
  colActions: {
    id: "directory.col.actions",
    defaultMessage: "Actions",
    description: "Column of row actions",
  },
  // ---- status chips
  statusTrial: {
    id: "directory.status.trial",
    defaultMessage: "Trial",
    description: "Status chip",
  },
  statusTrialDays: {
    id: "directory.status.trialDays",
    defaultMessage: "Trial {days, number} d",
    description: "Status chip: trial with days left, e.g. Trial 12 d",
  },
  statusPaid: { id: "directory.status.paid", defaultMessage: "Paid", description: "Status chip" },
  statusDemo: { id: "directory.status.demo", defaultMessage: "Demo", description: "Status chip" },
  statusReadOnly: {
    id: "directory.status.readOnly",
    defaultMessage: "Read-only",
    description: "Status chip",
  },
  statusArchived: {
    id: "directory.status.archived",
    defaultMessage: "Archived",
    description: "Status chip",
  },
  yes: { id: "directory.yes", defaultMessage: "Yes", description: "Payroll column value" },
  no: { id: "directory.no", defaultMessage: "No", description: "Payroll column value" },
  // ---- row actions
  rowActions: {
    id: "directory.row.actions",
    defaultMessage: "Actions for {name}",
    description: "Row menu button",
  },
  open: {
    id: "directory.row.open",
    defaultMessage: "Open",
    description: "Row action: open the organisation",
  },
  openNewTabFor: {
    id: "directory.row.openNewTabFor",
    defaultMessage: "Open in new tab: {name}",
    description: "Accessible name of a row's new-tab link",
  },
  openNewTab: {
    id: "directory.row.openNewTab",
    defaultMessage: "Open in new tab",
    description: "Row action",
  },
  // ---- filters
  filters: {
    id: "directory.filters.button",
    defaultMessage: "Filters",
    description: "Button opening the filters panel (shortcut F)",
  },
  filtersCount: {
    id: "directory.filters.buttonCount",
    defaultMessage: "Filters ({count, number})",
    description: "Filters button with the number of filters on",
  },
  filtersTitle: {
    id: "directory.filters.title",
    defaultMessage: "Filters",
    description: "Heading of the filters panel",
  },
  filtersClose: {
    id: "directory.filters.close",
    defaultMessage: "Close filters",
    description: "Close button of the panel",
  },
  filtersHint: {
    id: "directory.filters.hint",
    defaultMessage: "Numbers show how many organisations you would see with that option added.",
    description: "Under the filters panel",
  },
  filterCount: {
    id: "directory.filters.count",
    defaultMessage: ", {count, plural, one {# organisation} other {# organisations}}",
    description:
      "Screen-reader text right after a filter option's label: how many organisations it would show",
  },
  showArchived: {
    id: "directory.filters.showArchived",
    defaultMessage: "Show archived organisations",
    description: "Switch in the filters panel",
  },
  removeFilter: {
    id: "directory.filters.remove",
    defaultMessage: "Remove filter {chip}",
    description: "Accessible name of a chip's × button",
  },
  facetPackage: {
    id: "directory.facet.package",
    defaultMessage: "Package",
    description: "Filter group",
  },
  facetStatus: {
    id: "directory.facet.status",
    defaultMessage: "Status",
    description: "Filter group",
  },
  facetProvince: {
    id: "directory.facet.province",
    defaultMessage: "Province",
    description: "Filter group",
  },
  facetFye: {
    id: "directory.facet.fye",
    defaultMessage: "Fiscal year end",
    description: "Filter group",
  },
  facetGstCycle: {
    id: "directory.facet.gstCycle",
    defaultMessage: "GST/HST cycle",
    description: "Filter group",
  },
  facetPayroll: {
    id: "directory.facet.payroll",
    defaultMessage: "Payroll",
    description: "Filter group",
  },
  facetOverdue: {
    id: "directory.facet.overdue",
    defaultMessage: "Overdue items",
    description: "Filter group",
  },
  facetUnfiled: {
    id: "directory.facet.unfiled",
    defaultMessage: "Unfiled returns",
    description: "Filter group",
  },
  facetTag: { id: "directory.facet.tag", defaultMessage: "Tags", description: "Filter group" },
  facetGroup: {
    id: "directory.facet.group",
    defaultMessage: "Groups",
    description: "Filter group: the practice's groups (a group includes its sub-groups)",
  },
  groupBy: {
    id: "directory.groupBy.label",
    defaultMessage: "Group by",
    description: "Label of the directory's group-by choice",
  },
  groupByNone: {
    id: "directory.groupBy.none",
    defaultMessage: "No grouping",
    description: "Group-by choice: a flat list",
  },
  groupByGroup: {
    id: "directory.groupBy.group",
    defaultMessage: "Group",
    description: "Group-by choice: sections per practice group",
  },
  groupHeader: {
    id: "directory.groupHeader",
    defaultMessage: "{name} — {count, plural, one {# organisation} other {# organisations}}",
    description: "Group-by section header: group name and how many organisations it shows",
  },
  noGroup: {
    id: "directory.noGroup",
    defaultMessage: "No group",
    description: "Group-by section of organisations filed in no group",
  },
  groupToggle: {
    id: "directory.groupToggle",
    defaultMessage: "Show or hide {name}",
    description: "Accessible name of a group-by section's expand/collapse button",
  },
  facetNone: {
    id: "directory.facet.none",
    defaultMessage: "None in this list",
    description: "Filter group with no options",
  },
  // ---- saved views
  viewsTitle: {
    id: "directory.views.title",
    defaultMessage: "Saved views",
    description: "Heading of the saved views rail",
  },
  viewsAll: {
    id: "directory.views.all",
    defaultMessage: "All organisations",
    description: "The built-in view: no search or filter",
  },
  viewsDefault: {
    id: "directory.views.default",
    defaultMessage: "(default)",
    description: "Marker of the view that opens first",
  },
  viewsSave: {
    id: "directory.views.save",
    defaultMessage: "Save current view",
    description: "Rail button: save the current search, filters and columns",
  },
  viewsSaveChanges: {
    id: "directory.views.saveChanges",
    defaultMessage: "Save view",
    description: "Header button when the open view has changes",
  },
  viewsMenu: {
    id: "directory.views.menu",
    defaultMessage: "Options for view {name}",
    description: "Menu button of a saved view",
  },
  viewsUpdate: {
    id: "directory.views.update",
    defaultMessage: "Update with changes",
    description: "View menu item",
  },
  viewsRename: {
    id: "directory.views.rename",
    defaultMessage: "Rename…",
    description: "View menu item",
  },
  viewsSetDefault: {
    id: "directory.views.setDefault",
    defaultMessage: "Set as default",
    description: "View menu item",
  },
  viewsDelete: {
    id: "directory.views.delete",
    defaultMessage: "Delete…",
    description: "View menu item",
  },
  viewsNameLabel: {
    id: "directory.views.nameLabel",
    defaultMessage: "View name",
    description: "Field in the save/rename dialog",
  },
  viewsSaveTitle: {
    id: "directory.views.saveTitle",
    defaultMessage: "Save view",
    description: "Title of the save dialog",
  },
  viewsSaveBody: {
    id: "directory.views.saveBody",
    defaultMessage: "Saves the search, filters, columns and sort. Only you see your views.",
    description: "Text of the save dialog",
  },
  viewsRenameTitle: {
    id: "directory.views.renameTitle",
    defaultMessage: "Rename view",
    description: "Dialog title",
  },
  viewsDeleteTitle: {
    id: "directory.views.deleteTitle",
    defaultMessage: "Delete view “{name}”?",
    description: "Dialog title",
  },
  viewsDeleteBody: {
    id: "directory.views.deleteBody",
    defaultMessage: "The view is removed for you. Organisations are not changed.",
    description: "Delete dialog text",
  },
  viewsSaveButton: {
    id: "directory.views.saveButton",
    defaultMessage: "Save view",
    description: "Dialog primary button",
  },
  viewsRenameButton: {
    id: "directory.views.renameButton",
    defaultMessage: "Rename",
    description: "Dialog primary button",
  },
  viewsDeleteButton: {
    id: "directory.views.deleteButton",
    defaultMessage: "Delete view",
    description: "Dialog primary button",
  },
  cancel: { id: "directory.cancel", defaultMessage: "Cancel", description: "Dialog button" },
  close: { id: "directory.close", defaultMessage: "Close", description: "Dialog × button" },
  viewsNameRequired: {
    id: "directory.views.nameRequired",
    defaultMessage: "Enter a name for the view.",
    description: "Field error",
  },
  viewsFailed: {
    id: "directory.views.failed",
    defaultMessage: "The view couldn't be saved. Try again.",
    description: "Error when saving a view fails for another reason",
  },
  viewsLoadFailed: {
    id: "directory.views.loadFailed",
    defaultMessage: "Your saved views couldn't be loaded.",
    description: "Rail message when views fail to load",
  },
  viewSaved: {
    id: "directory.views.saved",
    defaultMessage: "View “{name}” saved",
    description: "Announced after saving",
  },
  viewDeleted: {
    id: "directory.views.deleted",
    defaultMessage: "View “{name}” deleted",
    description: "Announced after deleting",
  },
  // ---- states
  emptyTitle: {
    id: "directory.empty.title",
    defaultMessage: "Your practice has no organisations yet",
    description: "First-run empty state",
  },
  emptyBody: {
    id: "directory.empty.body",
    defaultMessage: "Create a client's organisation, or open the demo to look around.",
    description: "First-run empty state text",
  },
  emptyBodyNoDemo: {
    id: "directory.empty.bodyNoDemo",
    defaultMessage: "Create a client's organisation to get started.",
    description: "First-run empty state text when no demo organisation is offered",
  },
  emptyCreate: {
    id: "directory.empty.create",
    defaultMessage: "Create organisation",
    description: "Empty state action",
  },
  emptyDemo: {
    id: "directory.empty.demo",
    defaultMessage: "Open demo",
    description: "Empty state action",
  },
  noResultsTitle: {
    id: "directory.noResults.title",
    defaultMessage: "No organisations match",
    description: "No-results state",
  },
  noResultsBody: {
    id: "directory.noResults.body",
    defaultMessage:
      "Try another spelling or fewer filters. Archived organisations show only with “Show archived organisations”.",
    description: "No-results state text",
  },
  errorTitle: {
    id: "directory.error.title",
    defaultMessage: "The directory didn't load",
    description: "Error state",
  },
  errorBody: {
    id: "directory.error.body",
    defaultMessage: "Verify your connection, then try again. Nothing was changed.",
    description: "Error state text",
  },
  retry: {
    id: "directory.error.retry",
    defaultMessage: "Try again",
    description: "Error state button",
  },
  // ---- go to organisation (Ctrl/⌘+K)
  gotoTitle: {
    id: "directory.goto.title",
    defaultMessage: "Go to organisation",
    description: "Title of the Ctrl/⌘+K dialog",
  },
  gotoSearch: {
    id: "directory.goto.search",
    defaultMessage: "Organisation name, BN, owner or tag",
    description: "Search box of the dialog",
  },
  gotoResults: {
    id: "directory.goto.results",
    defaultMessage: "{count, plural, =0 {No organisations match} one {# result} other {# results}}",
    description: "Announced when results arrive",
  },
  gotoHint: {
    id: "directory.goto.hint",
    defaultMessage: "↑/↓ move · Enter opens · Ctrl/⌘+Enter opens in a new tab · Esc closes",
    description: "Keyboard hint at the bottom of the dialog",
  },
  gotoTyping: {
    id: "directory.goto.typing",
    defaultMessage: "Type part of a name or BN.",
    description: "Before typing",
  },
  gotoFailed: {
    id: "directory.goto.failed",
    defaultMessage: "Search failed. Try again.",
    description: "When the search request fails",
  },
  gotoOpenDirectory: {
    id: "directory.goto.openDirectory",
    defaultMessage: "Open the directory",
    description: "Link at the bottom of the dialog",
  },
  gotoKeys: {
    id: "directory.goto.keys",
    defaultMessage: "Ctrl+K",
    description: "Keyboard shortcut shown on the top bar button (⌘K on a Mac works too)",
  },
  gotoButton: {
    id: "directory.goto.button",
    defaultMessage: "Go to organisation…",
    description: "Top bar button opening the dialog (Ctrl/⌘+K)",
  },
  // ---- new organisation
  createTitle: {
    id: "directory.create.title",
    defaultMessage: "New organisation",
    description: "Dialog title",
  },
  createBody: {
    id: "directory.create.body",
    defaultMessage:
      "Starts the client’s trial, assigned to your practice. You can invite the owner afterwards.",
    description: "Dialog text",
  },
  createName: {
    id: "directory.create.name",
    defaultMessage: "Organisation name",
    description: "Field label",
  },
  createButton: {
    id: "directory.create.button",
    defaultMessage: "Create organisation",
    description: "Dialog primary button",
  },
  createNameRequired: {
    id: "directory.create.nameRequired",
    defaultMessage: "Enter the organisation's name.",
    description: "Field error",
  },
  createFailed: {
    id: "directory.create.failed",
    defaultMessage: "The organisation couldn't be created. Try again.",
    description: "Error when creating fails",
  },
});
