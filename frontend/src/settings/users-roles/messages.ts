/** Messages of Settings → Users and roles (A-03-T11…T14). */
import { defineMessages } from "@/i18n";

export const m = defineMessages({
  title: {
    id: "settings.usersRoles.title",
    defaultMessage: "Users and roles",
    description: "Heading of Settings → Users and roles",
  },
  intro: {
    id: "settings.usersRoles.intro",
    defaultMessage:
      "Who can work in this organisation, what each role allows, and how much each person can approve.",
    description: "Intro line under the Users and roles heading",
  },
  tabs: {
    id: "settings.usersRoles.tabs",
    defaultMessage: "Users and roles sections",
    description: "Accessible name of the tab list",
  },
  tabUsers: { id: "settings.usersRoles.tab.users", defaultMessage: "Users", description: "Tab" },
  tabRoles: { id: "settings.usersRoles.tab.roles", defaultMessage: "Roles", description: "Tab" },
  tabLimits: {
    id: "settings.usersRoles.tab.limits",
    defaultMessage: "Approval limits",
    description: "Tab",
  },
  loading: {
    id: "settings.usersRoles.loading",
    defaultMessage: "Loading users and roles…",
    description: "Busy text while the lists load",
  },
  loadFailed: {
    id: "settings.usersRoles.loadFailed",
    defaultMessage: "The list couldn't be loaded. Nothing was changed.",
    description: "Error state of a list",
  },
  retry: { id: "settings.usersRoles.retry", defaultMessage: "Try again", description: "Button" },
  close: { id: "settings.usersRoles.close", defaultMessage: "Close", description: "Dialog ×" },
  cancel: { id: "settings.usersRoles.cancel", defaultMessage: "Cancel", description: "Button" },
  // ---- users (A-03-T11)
  usersHeading: {
    id: "settings.usersRoles.users.heading",
    defaultMessage: "Users",
    description: "Heading of the members list",
  },
  usersTable: {
    id: "settings.usersRoles.users.table",
    defaultMessage: "People who can work in this organisation",
    description: "Caption of the members table",
  },
  colName: {
    id: "settings.usersRoles.users.colName",
    defaultMessage: "Name",
    description: "Column",
  },
  colRoles: {
    id: "settings.usersRoles.users.colRoles",
    defaultMessage: "Roles",
    description: "Column",
  },
  colAccess: {
    id: "settings.usersRoles.users.colAccess",
    defaultMessage: "Access",
    description: "Column: member, or through which practice",
  },
  colActions: {
    id: "settings.usersRoles.users.colActions",
    defaultMessage: "Actions",
    description: "Column with the row's buttons",
  },
  accessMember: {
    id: "settings.usersRoles.users.accessMember",
    defaultMessage: "Member",
    description: "Access column: belongs to the organisation",
  },
  accessPractice: {
    id: "settings.usersRoles.users.accessPractice",
    defaultMessage: "Through {practice} ({role})",
    description: "Access column: works here through a practice; {role} is the practice role",
  },
  mainRole: {
    id: "settings.usersRoles.users.mainRole",
    defaultMessage: "{role} (main role)",
    description: "Role chip of the member's main (membership) role",
  },
  removeRole: {
    id: "settings.usersRoles.users.removeRole",
    defaultMessage: "Take {role} away from {name}",
    description: "Accessible name of the × on a role chip",
  },
  giveRole: {
    id: "settings.usersRoles.users.giveRole",
    defaultMessage: "Give a role",
    description: "Row button: opens the give-a-role dialog",
  },
  giveRoleTo: {
    id: "settings.usersRoles.users.giveRoleTo",
    defaultMessage: "Give a role to {name}",
    description: "Title of the give-a-role dialog; also the row button's accessible name",
  },
  giveRoleHelp: {
    id: "settings.usersRoles.users.giveRoleHelp",
    defaultMessage:
      "A main role replaces the one they have. A custom role is added to what they already have.",
    description: "Give-a-role dialog explanation",
  },
  giveRolePracticeHelp: {
    id: "settings.usersRoles.users.giveRolePracticeHelp",
    defaultMessage:
      "{name} works here through their practice, so you can add custom roles; their practice role stays.",
    description: "Give-a-role dialog explanation for practice staff",
  },
  roleLabel: { id: "settings.usersRoles.users.role", defaultMessage: "Role", description: "Label" },
  rolePlaceholder: {
    id: "settings.usersRoles.users.rolePlaceholder",
    defaultMessage: "Choose a role",
    description: "Role select placeholder",
  },
  groupMain: {
    id: "settings.usersRoles.users.groupMain",
    defaultMessage: "Main roles",
    description: "Role select group: system organisation roles",
  },
  groupCustom: {
    id: "settings.usersRoles.users.groupCustom",
    defaultMessage: "Custom roles",
    description: "Role select group: the organisation's custom roles",
  },
  give: {
    id: "settings.usersRoles.users.give",
    defaultMessage: "Give role",
    description: "Button",
  },
  roleGiven: {
    id: "settings.usersRoles.users.roleGiven",
    defaultMessage: "{name} now has the role {role}",
    description: "Toast after giving a role",
  },
  roleTaken: {
    id: "settings.usersRoles.users.roleTaken",
    defaultMessage: "{role} taken away from {name}",
    description: "Toast after taking a role away",
  },
  noUsers: {
    id: "settings.usersRoles.users.none",
    defaultMessage: "Nobody else works here yet. Invite your team to share the work.",
    description: "Empty members list",
  },
  invite: {
    id: "settings.usersRoles.users.invite",
    defaultMessage: "Invite a user",
    description: "Button / dialog title",
  },
  inviteHelp: {
    id: "settings.usersRoles.users.inviteHelp",
    defaultMessage:
      "They get an email with a link that works once and expires in 7 days. You can change their role later.",
    description: "Invite dialog explanation",
  },
  email: { id: "settings.usersRoles.users.email", defaultMessage: "Email", description: "Label" },
  emailInvalid: {
    id: "settings.usersRoles.users.emailInvalid",
    defaultMessage: "Enter an email address like 'sam@refined.ca'.",
    description: "Validation",
  },
  sendInvite: {
    id: "settings.usersRoles.users.sendInvite",
    defaultMessage: "Send invitation",
    description: "Button",
  },
  invited: {
    id: "settings.usersRoles.users.invited",
    defaultMessage: "Invitation sent to {email}",
    description: "Toast after inviting",
  },
  pendingHeading: {
    id: "settings.usersRoles.users.pending",
    defaultMessage: "Invitations waiting for an answer",
    description: "Heading of the pending invitations list",
  },
  pendingRow: {
    id: "settings.usersRoles.users.pendingRow",
    defaultMessage: "{email} · {role} · invited by {inviter} · expires {expires}",
    description: "One pending invitation",
  },
  failed: {
    id: "settings.usersRoles.failed",
    defaultMessage: "That didn't work and nothing was changed. Try again in a moment.",
    description: "Generic failure of a change",
  },
  // ---- explain (A-03-T14)
  deniedTitle: {
    id: "settings.usersRoles.denied.title",
    defaultMessage: "You can't see this yet",
    description: "Permission refusal panel heading",
  },
  notFoundTitle: {
    id: "settings.usersRoles.notFound.title",
    defaultMessage: "This organisation isn't available",
    description: "404 panel heading",
  },
  notFoundBody: {
    id: "settings.usersRoles.notFound.body",
    defaultMessage:
      "It doesn't exist, or you no longer have access to it. Choose another organisation from the switcher.",
    description: "404 panel body",
  },
});

/** Organisation role keys → names, for invitations (the API sends the key). */
export const orgRoleNames = defineMessages({
  role: {
    id: "settings.usersRoles.orgRole",
    defaultMessage:
      "{role, select, owner {Owner} admin {Admin} accountant_delegate {Accountant delegate} sales {Sales} purchasing {Purchasing} payroll {Payroll} hr {HR} employee {Employee} other {{role}}}",
    description: "Organisation role named in a pending invitation",
  },
});

/** Roles tab and role editor (A-03-T12). */
export const rm = defineMessages({
  heading: {
    id: "settings.usersRoles.roles.heading",
    defaultMessage: "Roles",
    description: "Heading of the roles list",
  },
  newRole: {
    id: "settings.usersRoles.roles.new",
    defaultMessage: "New role",
    description: "Button: create a custom role",
  },
  listLabel: {
    id: "settings.usersRoles.roles.list",
    defaultMessage: "Roles of this organisation",
    description: "Accessible name of the roles list",
  },
  system: {
    id: "settings.usersRoles.roles.system",
    defaultMessage: "System role",
    description: "Badge: a role defined by Numo9 (read-only)",
  },
  custom: {
    id: "settings.usersRoles.roles.custom",
    defaultMessage: "Custom role",
    description: "Badge: a role made by this organisation",
  },
  practiceRole: {
    id: "settings.usersRoles.roles.practiceRole",
    defaultMessage: "Practice role",
    description: "Badge: given by an accounting practice to its staff",
  },
  holders: {
    id: "settings.usersRoles.roles.holders",
    defaultMessage: "{count, plural, =0 {Nobody has it} one {# person} other {# people}}",
    description: "How many people hold the role here",
  },
  permissionCount: {
    id: "settings.usersRoles.roles.permissionCount",
    defaultMessage: "{count, plural, one {# permission} other {# permissions}}",
    description: "Number of permissions in a role",
  },
  stats: {
    id: "settings.usersRoles.roles.stats",
    defaultMessage: "{holders} · {permissions}",
    description: "Under a role's name: who holds it · how many permissions",
  },
  open: {
    id: "settings.usersRoles.roles.open",
    defaultMessage: "Open {role}",
    description: "Link to a role (view or edit)",
  },
  copyRole: {
    id: "settings.usersRoles.roles.copy",
    defaultMessage: "Copy {role}",
    description: "Link: new custom role starting from this one",
  },
  saved: {
    id: "settings.usersRoles.roles.saved",
    defaultMessage: "Role {role} saved",
    description: "Status after saving a role",
  },
  deleted: {
    id: "settings.usersRoles.roles.deleted",
    defaultMessage: "Role {role} deleted",
    description: "Status after deleting a role",
  },
  // ---- editor
  editorNew: {
    id: "settings.usersRoles.editor.new",
    defaultMessage: "New custom role",
    description: "Heading of the role editor when creating",
  },
  editorView: {
    id: "settings.usersRoles.editor.view",
    defaultMessage: "{role} (system role)",
    description: "Heading of the role editor showing a read-only system role",
  },
  editorEdit: {
    id: "settings.usersRoles.editor.edit",
    defaultMessage: "Edit {role}",
    description: "Heading of the role editor when editing a custom role",
  },
  back: {
    id: "settings.usersRoles.editor.back",
    defaultMessage: "Back to roles",
    description: "Link back to the roles tab",
  },
  systemReadOnly: {
    id: "settings.usersRoles.editor.systemReadOnly",
    defaultMessage:
      "System roles are defined by Numo9 and can't be changed. Copy this one into a custom role to change what it allows.",
    description: "Notice on a system role",
  },
  copyIntoCustom: {
    id: "settings.usersRoles.editor.copyIntoCustom",
    defaultMessage: "Copy into a custom role",
    description: "Button on a system role",
  },
  name: { id: "settings.usersRoles.editor.name", defaultMessage: "Name", description: "Label" },
  nameRequired: {
    id: "settings.usersRoles.editor.nameRequired",
    defaultMessage: "Give the role a name, e.g. 'Showroom staff'.",
    description: "Validation",
  },
  description: {
    id: "settings.usersRoles.editor.description",
    defaultMessage: "Description (optional)",
    description: "Label",
  },
  copyFrom: {
    id: "settings.usersRoles.editor.copyFrom",
    defaultMessage: "Copy from role",
    description: "Label of the select that copies another role's permissions",
  },
  copyFromPlaceholder: {
    id: "settings.usersRoles.editor.copyFromPlaceholder",
    defaultMessage: "Start from an existing role",
    description: "Placeholder",
  },
  copied: {
    id: "settings.usersRoles.editor.copied",
    defaultMessage: "Permissions copied from {role}. Adjust them below.",
    description: "Status after copying",
  },
  search: {
    id: "settings.usersRoles.editor.search",
    defaultMessage: "Search permissions",
    description: "Label of the permission search box",
  },
  searchHint: {
    id: "settings.usersRoles.editor.searchHint",
    defaultMessage: "Type what someone should be able to do, e.g. 'invite' or 'settings'.",
    description: "Hint under the permission search box",
  },
  selected: {
    id: "settings.usersRoles.editor.selected",
    defaultMessage: "{selected} of {total} permissions selected",
    description: "Count above the permission matrix",
  },
  matrix: {
    id: "settings.usersRoles.editor.matrix",
    defaultMessage: "What this role allows",
    description: "Heading of the permission matrix",
  },
  allInModule: {
    id: "settings.usersRoles.editor.allInModule",
    defaultMessage: "Everything in {module}",
    description: "Checkbox selecting every permission of a module",
  },
  noMatch: {
    id: "settings.usersRoles.editor.noMatch",
    defaultMessage: "No permission matches “{query}”. Try another word.",
    description: "Empty search result",
  },
  ownerOnly: {
    id: "settings.usersRoles.editor.ownerOnly",
    defaultMessage: "Owners only by default",
    description: "Badge on permissions that broad roles don't get",
  },
  notYours: {
    id: "settings.usersRoles.editor.notYours",
    defaultMessage: "You don't have this permission, so you can't give it.",
    description: "Hint on a permission the editor may not grant",
  },
  save: {
    id: "settings.usersRoles.editor.save",
    defaultMessage: "Save role",
    description: "Button",
  },
  delete: {
    id: "settings.usersRoles.editor.delete",
    defaultMessage: "Delete role",
    description: "Button",
  },
  deleteConfirm: {
    id: "settings.usersRoles.editor.deleteConfirm",
    defaultMessage: "Delete {role}? Its approval limits are removed too.",
    description: "Delete confirmation dialog title",
  },
  deleteBody: {
    id: "settings.usersRoles.editor.deleteBody",
    defaultMessage: "Nobody holds this role now. This can't be undone.",
    description: "Delete confirmation dialog body",
  },
  inUse: {
    id: "settings.usersRoles.editor.inUse",
    defaultMessage:
      "{count, plural, one {# person holds} other {# people hold}} this role. Take it away from them on the Users tab before deleting it.",
    description: "Why delete is unavailable",
  },
});
