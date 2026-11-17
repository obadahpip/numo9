import { defineMessages } from "@/i18n";

/** Practice groups and tags (V-02-T09…T11): tree, move, tag picker, delete dialog. */
export const m = defineMessages({
  title: {
    id: "groups.title",
    defaultMessage: "Groups and tags",
    description: "Heading of the practice's groups and tags screen",
  },
  breadcrumb: {
    id: "groups.breadcrumb",
    defaultMessage: "Groups",
    description: "Breadcrumb of the practice's groups and tags screen",
  },
  intro: {
    id: "groups.intro",
    defaultMessage:
      "Groups organise your clients (up to 5 levels). Staff assigned to a group work on every client in it and in its sub-groups.",
    description: "Explanation under the groups heading",
  },
  treeLabel: {
    id: "groups.tree.label",
    defaultMessage: "Practice groups",
    description: "Accessible name of the group tree",
  },
  empty: {
    id: "groups.empty",
    defaultMessage: "No groups yet. Create one to organise your clients.",
    description: "Group tree with no groups",
  },
  counts: {
    id: "groups.counts",
    defaultMessage:
      "{organisations, plural, one {# organisation} other {# organisations}} · {staff, plural, one {# staff member} other {# staff}}",
    description: "Counts next to a group in the tree (organisations in the group and sub-groups)",
  },
  newGroup: {
    id: "groups.new",
    defaultMessage: "New group",
    description: "Button creating a top-level group",
  },
  addSubGroup: {
    id: "groups.addSub.label",
    defaultMessage: "Add sub-group to {name}",
    description: "Accessible name of the button adding a sub-group",
  },
  addSubGroupShort: {
    id: "groups.addSub.short",
    defaultMessage: "Add sub-group",
    description: "Button adding a sub-group",
  },
  rename: {
    id: "groups.rename.button",
    defaultMessage: "Rename",
    description: "Button renaming a group",
  },
  renameFor: {
    id: "groups.rename.for",
    defaultMessage: "Rename {name}",
    description: "Accessible name of the rename button",
  },
  moveTo: {
    id: "groups.moveTo.button",
    defaultMessage: "Move to…",
    description: "Button opening the keyboard alternative to drag and drop",
  },
  moveToFor: {
    id: "groups.moveTo.for",
    defaultMessage: "Move {name} to…",
    description: "Accessible name of the move button",
  },
  moveTitle: {
    id: "groups.move.title",
    defaultMessage: "Move {name}",
    description: "Title of the move dialog",
  },
  moveBody: {
    id: "groups.move.body",
    defaultMessage:
      "Choose where {name} goes. Its sub-groups move with it; staff access follows the new place.",
    description: "Text of the move dialog",
  },
  moveTop: {
    id: "groups.move.top",
    defaultMessage: "Top level",
    description: "Move target: no parent group",
  },
  moveConfirm: {
    id: "groups.move.confirm",
    defaultMessage: "Move",
    description: "Button confirming the move",
  },
  moveNone: {
    id: "groups.move.none",
    defaultMessage: "There's nowhere else this group can go (5 levels at most).",
    description: "Move dialog with no valid target",
  },
  moved: {
    id: "groups.moved",
    defaultMessage: "{name} moved.",
    description: "Announcement after a move",
  },
  dragHint: {
    id: "groups.dragHint",
    defaultMessage:
      "Drag a group onto another to move it there, or onto “Top level”. With the keyboard, use “Move to…”.",
    description: "Hint under the tree",
  },
  dropTop: {
    id: "groups.dropTop",
    defaultMessage: "Drop here to move to the top level",
    description: "Drop zone for moving a group to the top level",
  },
  nameLabel: {
    id: "groups.name.label",
    defaultMessage: "Group name",
    description: "Label of the group name field",
  },
  createTitle: {
    id: "groups.create.title",
    defaultMessage: "New group",
    description: "Title of the new group dialog",
  },
  createSubTitle: {
    id: "groups.create.subTitle",
    defaultMessage: "New sub-group of {name}",
    description: "Title of the new sub-group dialog",
  },
  renameTitle: {
    id: "groups.rename.title",
    defaultMessage: "Rename {name}",
    description: "Title of the rename dialog",
  },
  save: { id: "groups.save", defaultMessage: "Save", description: "Button saving a group" },
  cancel: { id: "groups.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "groups.close", defaultMessage: "Close", description: "Dialog close button" },
  loading: { id: "groups.loading", defaultMessage: "Loading groups…", description: "Loading" },
  loadFailed: {
    id: "groups.loadFailed",
    defaultMessage: "The groups couldn't be loaded.",
    description: "Error loading the groups",
  },
  retry: { id: "groups.retry", defaultMessage: "Try again", description: "Retry button" },
  tagsTitle: {
    id: "groups.tags.title",
    defaultMessage: "Tags",
    description: "Heading of the practice's tags",
  },
  tagsIntro: {
    id: "groups.tags.intro",
    defaultMessage:
      "Tags mark clients across groups (“Year-end soon”). Type a new name to create one.",
    description: "Explanation of the tags section",
  },
  tagsEmpty: {
    id: "groups.tags.empty",
    defaultMessage: "No tags yet.",
    description: "Tags section with no tags",
  },
  tagUsage: {
    id: "groups.tags.usage",
    defaultMessage: "{count, plural, one {# organisation} other {# organisations}}",
    description: "How many organisations have the tag",
  },
  tagPickerLabel: {
    id: "groups.tags.picker",
    defaultMessage: "Find or create a tag",
    description: "Label of the tag picker",
  },
  tagCreate: {
    id: "groups.tags.create",
    defaultMessage: "Create tag “{name}” ({colour})",
    description: "Tag picker option creating a new tag with the chosen colour",
  },
  tagColour: {
    id: "groups.tags.colour",
    defaultMessage: "Colour of the new tag",
    description: "Legend of the colour choice for a new tag",
  },
  tagColourName: {
    id: "groups.tags.colourName",
    defaultMessage: "({colour})",
    description: "Screen-reader text after a tag's name: its colour's name",
  },
  tagCreated: {
    id: "groups.tags.created",
    defaultMessage: "Tag {name} created.",
    description: "Announcement after creating a tag",
  },
  colourRed: { id: "groups.colour.red", defaultMessage: "Red", description: "Tag colour" },
  colourOrange: { id: "groups.colour.orange", defaultMessage: "Orange", description: "Tag colour" },
  colourAmber: { id: "groups.colour.amber", defaultMessage: "Amber", description: "Tag colour" },
  colourOlive: { id: "groups.colour.olive", defaultMessage: "Olive", description: "Tag colour" },
  colourGreen: { id: "groups.colour.green", defaultMessage: "Green", description: "Tag colour" },
  colourTeal: { id: "groups.colour.teal", defaultMessage: "Teal", description: "Tag colour" },
  colourCyan: { id: "groups.colour.cyan", defaultMessage: "Cyan", description: "Tag colour" },
  colourBlue: { id: "groups.colour.blue", defaultMessage: "Blue", description: "Tag colour" },
  colourIndigo: { id: "groups.colour.indigo", defaultMessage: "Indigo", description: "Tag colour" },
  colourViolet: { id: "groups.colour.violet", defaultMessage: "Violet", description: "Tag colour" },
  colourMagenta: {
    id: "groups.colour.magenta",
    defaultMessage: "Magenta",
    description: "Tag colour",
  },
  colourSlate: { id: "groups.colour.slate", defaultMessage: "Slate", description: "Tag colour" },
  failed: {
    id: "groups.failed",
    defaultMessage: "That didn't work. Try again.",
    description: "Generic failure of a group change",
  },
});
