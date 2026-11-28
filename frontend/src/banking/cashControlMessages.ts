import { defineMessages } from "@/i18n";

/** The negative-balance panel (F-07-T07) and the policy settings (F-07-T08). */
export const cash = defineMessages({
  title: {
    id: "banking.cash.title",
    defaultMessage: "This would take a bank or cash account below zero",
    description: "Heading of the inline negative-balance panel in a form",
  },
  warnBody: {
    id: "banking.cash.warnBody",
    defaultMessage:
      "You may save it anyway: say why. The reason is kept with the journal and shown to your adviser.",
    description: "Negative-balance panel, warning state",
  },
  blockBody: {
    id: "banking.cash.blockBody",
    defaultMessage:
      "This organisation doesn't let it go below zero. Record the money coming in first, for example with a transfer.",
    description: "Negative-balance panel, block state",
  },
  overrider: {
    id: "banking.cash.overrider",
    defaultMessage:
      "Who can override: your adviser, or someone allowed to approve negative balances. The owner can change the rule in Banking settings.",
    description: "Negative-balance panel, block state: who can override",
  },
  remedies: {
    id: "banking.cash.remedies",
    defaultMessage: "Ways to fix it",
    description: "Accessible name of the remedy buttons group",
  },
  reason: {
    id: "banking.cash.reason",
    defaultMessage: "Reason for saving it anyway",
    description: "Label of the reason field in the negative-balance panel",
  },
  reasonHint: {
    id: "banking.cash.reasonHint",
    defaultMessage: "At least {min} characters.",
    description: "Hint under the reason field",
  },
  receiveInto: {
    id: "banking.cash.receiveInto",
    defaultMessage: "Record money coming in",
    description: "Remedy button: open receive money for the account",
  },

  settingsLink: {
    id: "banking.cash.settingsLink",
    defaultMessage: "Banking settings",
    description: "Link from the banking home to the banking settings",
  },
  settingsTitle: {
    id: "banking.cash.settingsTitle",
    defaultMessage: "Banking settings",
    description: "Heading of the banking settings page",
  },
  policyHeading: {
    id: "banking.cash.policyHeading",
    defaultMessage: "When a posting would take an account below zero",
    description: "Section heading: the negative-balance policy",
  },
  policyIntro: {
    id: "banking.cash.policyIntro",
    defaultMessage:
      "Numo9 checks every spend, payment, transfer, journal and payroll run before it is saved. Choose what happens for each type of account. Credit cards, lines of credit and loans are never checked: they are amounts you owe.",
    description: "Explanation of the negative-balance policy",
  },
  colType: {
    id: "banking.cash.colType",
    defaultMessage: "Account type",
    description: "Policy table column",
  },
  colStandard: {
    id: "banking.cash.colStandard",
    defaultMessage: "Everyone else",
    description: "Policy table column: people who aren't advisers",
  },
  colAdviser: {
    id: "banking.cash.colAdviser",
    defaultMessage: "Advisers",
    description: "Policy table column: the organisation's advisers",
  },
  standardFor: {
    id: "banking.cash.standardFor",
    defaultMessage: "{type}: everyone else",
    description: "Accessible label of the select for people who aren't advisers",
  },
  adviserFor: {
    id: "banking.cash.adviserFor",
    defaultMessage: "{type}: advisers",
    description: "Accessible label of the select for advisers",
  },
  actionAllow: {
    id: "banking.cash.actionAllow",
    defaultMessage: "Allow",
    description: "Policy choice: post without asking",
  },
  actionWarn: {
    id: "banking.cash.actionWarn",
    defaultMessage: "Warn — ask for a reason",
    description: "Policy choice: warn and ask for a reason",
  },
  actionBlock: {
    id: "banking.cash.actionBlock",
    defaultMessage: "Block",
    description: "Policy choice: refuse",
  },
  defaultIs: {
    id: "banking.cash.defaultIs",
    defaultMessage: "Default: {standard} / {adviser}",
    description: "The default actions of a type",
  },
  save: {
    id: "banking.cash.save",
    defaultMessage: "Save changes",
    description: "Button: save the policy",
  },
  saved: {
    id: "banking.cash.saved",
    defaultMessage: "Saved. The next posting follows the new rule.",
    description: "Status after saving the policy",
  },
  saveFailed: {
    id: "banking.cash.saveFailed",
    defaultMessage: "The settings couldn't be saved. Try again.",
    description: "Error saving the policy",
  },
  loadFailed: {
    id: "banking.cash.loadFailed",
    defaultMessage: "The banking settings couldn't be loaded.",
    description: "Error loading the policy",
  },
  retry: {
    id: "banking.cash.retry",
    defaultMessage: "Try again",
    description: "Retry button",
  },
});
