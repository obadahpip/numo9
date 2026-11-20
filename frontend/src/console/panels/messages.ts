import { defineMessages } from "@/i18n";

export const m = defineMessages({
  foundingTitle: {
    id: "console.panels.foundingTitle",
    defaultMessage: "Founding offer",
    description: "Console home panel heading (U-06-T13)",
  },
  foundingCounter: {
    id: "console.panels.foundingCounter",
    defaultMessage: "{allocated, number}/{cap, number}",
    description: "Founding places given out of the cap, e.g. 427/1,000",
  },
  foundingCounterLabel: {
    id: "console.panels.foundingCounterLabel",
    defaultMessage: "{allocated, number} of {cap, number} founding places given",
    description: "Accessible text of the founding counter",
  },
  foundingLeft: {
    id: "console.panels.foundingLeft",
    defaultMessage: "{remaining, number} left",
    description: "Founding places still available",
  },
  foundingComplete: {
    id: "console.panels.foundingComplete",
    defaultMessage: "Offer complete",
    description: "No founding place left",
  },
  foundingOpen: {
    id: "console.panels.foundingOpen",
    defaultMessage: "See founding places",
    description: "Link to the founding offer screen",
  },
  demosTitle: {
    id: "console.panels.demosTitle",
    defaultMessage: "Demo organisations",
    description: "Console home panel heading (U-06-T13)",
  },
  demosSummary: {
    id: "console.panels.demosSummary",
    defaultMessage:
      "{open, plural, =0 {No demo open} one {# demo open} other {# demos open}} · {soon, plural, =0 {none purged this week} other {# purged within 7 days}} · seed version {version, number}",
    description: "Demo manager summary",
  },
  demosRule: {
    id: "console.panels.demosRule",
    defaultMessage: "A demo is purged {days, number} days after its last activity.",
    description: "Inactivity purge rule",
  },
  demosCaption: {
    id: "console.panels.demosCaption",
    defaultMessage: "Open demo organisations",
    description: "Table caption",
  },
  demoName: { id: "console.panels.demoName", defaultMessage: "Demo", description: "Column" },
  demoLastActive: {
    id: "console.panels.demoLastActive",
    defaultMessage: "Last activity",
    description: "Column",
  },
  demoNever: {
    id: "console.panels.demoNever",
    defaultMessage: "Never used",
    description: "Demo never opened after creation",
  },
  demoPurgeOn: {
    id: "console.panels.demoPurgeOn",
    defaultMessage: "Purged on",
    description: "Column: the day the inactivity purge takes it",
  },
  demoMembers: {
    id: "console.panels.demoMembers",
    defaultMessage: "People",
    description: "Column: members of the demo",
  },
  demoActions: {
    id: "console.panels.demoActions",
    defaultMessage: "Actions",
    description: "Column",
  },
  purge: { id: "console.panels.purge", defaultMessage: "Purge now", description: "Button" },
  purgeLabel: {
    id: "console.panels.purgeLabel",
    defaultMessage: "Purge now: {name}",
    description: "Accessible name of the purge button",
  },
  purgeTitle: {
    id: "console.panels.purgeTitle",
    defaultMessage: "Purge {name} now?",
    description: "Confirm dialog title",
  },
  purgeBody: {
    id: "console.panels.purgeBody",
    defaultMessage:
      "Its data is deleted and the people using it lose access. Real organisations are never affected.",
    description: "Confirm dialog text",
  },
  purged: {
    id: "console.panels.purged",
    defaultMessage: "{name} purged.",
    description: "Status after a purge",
  },
  purgeFailed: {
    id: "console.panels.purgeFailed",
    defaultMessage: "The demo wasn't purged. Only platform owners can purge a demo.",
    description: "Purge error",
  },
  cancel: { id: "console.panels.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "console.panels.close", defaultMessage: "Close", description: "Dialog close" },
  demosEmpty: {
    id: "console.panels.demosEmpty",
    defaultMessage: "No demo is open right now.",
    description: "Empty demo list",
  },
  loadFailed: {
    id: "console.panels.loadFailed",
    defaultMessage: "This panel didn't load",
    description: "Panel error",
  },
  retry: { id: "console.panels.retry", defaultMessage: "Try again", description: "Button" },
});
