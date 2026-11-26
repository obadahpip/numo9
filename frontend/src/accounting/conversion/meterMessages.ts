import { defineMessages } from "@/i18n";

/** Difference meter and Finalise (C-05-T11). */
export const mm = defineMessages({
  region: {
    id: "conversion.meter.region",
    defaultMessage: "Conversion difference",
    description: "Accessible name of the sticky meter",
  },
  totals: {
    id: "conversion.meter.totals",
    defaultMessage: "Debits {debits} · Credits {credits} · Difference {difference}",
    description: "The meter's figures",
  },
  unavailable: {
    id: "conversion.meter.unavailable",
    defaultMessage: "— Finalise unavailable",
    description: "After the figures when Finalise is disabled",
  },
  ready: {
    id: "conversion.meter.ready",
    defaultMessage: "— Balanced, ready to finalise",
    description: "After the figures when Finalise is possible",
  },
  finalise: { id: "conversion.meter.finalise", defaultMessage: "Finalise", description: "Button" },
  finalising: {
    id: "conversion.meter.finalising",
    defaultMessage: "Finalising…",
    description: "Button while posting",
  },
  why: {
    id: "conversion.meter.why",
    defaultMessage: "Why Finalise is unavailable",
    description: "Accessible name of the reasons list",
  },
  unbalanced: {
    id: "conversion.meter.unbalanced",
    defaultMessage: "The balances are out by {difference}: debits must equal credits.",
    description: "Reason (names the difference)",
  },
  empty: {
    id: "conversion.meter.empty",
    defaultMessage: "Enter at least one opening balance.",
    description: "Reason",
  },
  unreadable: {
    id: "conversion.meter.unreadable",
    defaultMessage:
      "{count, plural, one {# amount isn't a number} other {# amounts aren't numbers}} yet.",
    description: "Reason",
  },
  finalised: {
    id: "conversion.meter.finalised",
    defaultMessage: "The conversion is finalised.",
    description: "Reason",
  },
  confirmTitle: {
    id: "conversion.meter.confirmTitle",
    defaultMessage: "Finalise the conversion?",
    description: "Dialog title",
  },
  confirmBody: {
    id: "conversion.meter.confirmBody",
    defaultMessage:
      "One opening journal is posted, dated {date}. The balances and documents can't be edited afterwards: corrections are correcting journals, posted by an adviser.",
    description: "Dialog text",
  },
  confirmLock: {
    id: "conversion.meter.confirmLock",
    defaultMessage:
      "Balances will be locked: the general ledger, sales and purchases close to {date} for everyone except advisers.",
    description: "Dialog text when lock balances is on",
  },
  confirm: { id: "conversion.meter.confirm", defaultMessage: "Finalise", description: "Button" },
  cancel: { id: "conversion.meter.cancel", defaultMessage: "Cancel", description: "Button" },
  failed: {
    id: "conversion.meter.failed",
    defaultMessage: "That didn't work and nothing was posted. Try again in a moment.",
    description: "Error",
  },
});
