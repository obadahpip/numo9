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
