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
});
