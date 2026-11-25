import { defineMessages, type MessageDescriptor } from "@/i18n";

import type { StopReason } from "./api";

/** Stop & restart filing (G-03b-T10…T12). */
export const smsg = defineMessages({
  dangerTitle: {
    id: "tax.filing.stop.title",
    defaultMessage: "Stop filing",
    description: "Danger-zone card heading (G-03b)",
  },
  dangerIntro: {
    id: "tax.filing.stop.intro",
    defaultMessage:
      "Use this when the registration is cancelled, you become a small supplier, or it is suspended. Filed periods are never changed.",
    description: "Danger-zone card text",
  },
  lastDay: {
    id: "tax.filing.stop.lastDay",
    defaultMessage: "Last day registered",
    description: "Field: the stop date",
  },
  reason: { id: "tax.filing.stop.reason", defaultMessage: "Reason", description: "Field" },
  note: {
    id: "tax.filing.stop.note",
    defaultMessage: "Note (kept in the history)",
    description: "Field",
  },
  reviewImpact: {
    id: "tax.filing.stop.review",
    defaultMessage: "Review the impact",
    description: "Button: preview the stop",
  },
  impactTitle: {
    id: "tax.filing.stop.impactTitle",
    defaultMessage: "What happens",
    description: "Heading of the stop's impact preview",
  },
  impactRemoved: {
    id: "tax.filing.stop.impactRemoved",
    defaultMessage:
      "{count, plural, =0 {No period after {date} to remove.} one {# period after {date} will be removed.} other {# periods after {date} will be removed.}}",
    description: "Impact: unfiled periods removed",
  },
  impactFinal: {
    id: "tax.filing.stop.impactFinal",
    defaultMessage: "Your final return covers {start} – {end}.",
    description: "Impact: the last period, cut at the stop date",
  },
  impactDocuments: {
    id: "tax.filing.stop.impactDocuments",
    defaultMessage:
      "{count, plural, one {# document dated after {date} uses GST/HST or QST codes: review it.} other {# documents dated after {date} use GST/HST or QST codes: review them.}}",
    description: "Impact: documents after the stop with the registration's codes",
  },
  impactOutOfScope: {
    id: "tax.filing.stop.impactOutOfScope",
    defaultMessage: "New sales after {date} default to Out of scope.",
    description: "Impact: the default flip (tax setting)",
  },
  documentLink: {
    id: "tax.filing.stop.documentLink",
    defaultMessage: "{number} ({date})",
    description: "Link to a post-stop document",
  },
  draft: { id: "tax.filing.stop.draft", defaultMessage: "Draft", description: "Unnumbered doc" },
  confirmLabel: {
    id: "tax.filing.stop.confirmLabel",
    defaultMessage: "Type the registration number {number} to confirm",
    description: "Typed confirmation field",
  },
  confirmButton: {
    id: "tax.filing.stop.confirm",
    defaultMessage: "Stop filing",
    description: "Danger button",
  },
  confirmHint: {
    id: "tax.filing.stop.confirmHint",
    defaultMessage: "The button stays disabled until the number matches.",
    description: "Hint under the typed confirmation",
  },
  stopped: {
    id: "tax.filing.stop.stopped",
    defaultMessage: "Filing stopped: the last day registered is {date}.",
    description: "Status after a stop / banner while stopped",
  },
  restartButton: {
    id: "tax.filing.restart.button",
    defaultMessage: "Restart filing",
    description: "Button opening the restart wizard",
  },
  restartTitle: {
    id: "tax.filing.restart.title",
    defaultMessage: "Restart filing",
    description: "Wizard title",
  },
  restartDate: {
    id: "tax.filing.restart.date",
    defaultMessage: "Registered again from",
    description: "Field",
  },
  restartFrequency: {
    id: "tax.filing.restart.frequency",
    defaultMessage: "Filing frequency",
    description: "Field",
  },
  restartHint: {
    id: "tax.filing.restart.hint",
    defaultMessage: "The date must be after the last day registered ({date}).",
    description: "Hint",
  },
  restartPreview: {
    id: "tax.filing.restart.preview",
    defaultMessage: "Preview",
    description: "Button",
  },
  restartConfirm: {
    id: "tax.filing.restart.confirm",
    defaultMessage: "Restart",
    description: "Button",
  },
  back: { id: "tax.filing.restart.back", defaultMessage: "Back", description: "Button" },
  cancel: { id: "tax.filing.stop.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "tax.filing.stop.close", defaultMessage: "Close", description: "Dialog close" },
  failed: {
    id: "tax.filing.stop.failed",
    defaultMessage: "That didn't work and nothing was changed. Try again in a moment.",
    description: "Generic error",
  },
  notRegistered: {
    id: "tax.filing.gap.label",
    defaultMessage: "Not registered",
    description: "Timeline band between a stop and a restart",
  },
  gapDates: {
    id: "tax.filing.gap.dates",
    defaultMessage: "{start} – {end}",
    description: "Dates of a not-registered band",
  },
  gapOpen: {
    id: "tax.filing.gap.open",
    defaultMessage: "From {start}",
    description: "Dates of a band still open (stopped)",
  },
  gapName: {
    id: "tax.filing.gap.name",
    defaultMessage: "Not registered: {dates}",
    description: "Accessible name of the band",
  },
  stopMarker: {
    id: "tax.filing.marker.stop",
    defaultMessage: "Stopped {date}",
    description: "Timeline marker of a stop",
  },
  restartMarker: {
    id: "tax.filing.marker.restart",
    defaultMessage: "Restarted {date}",
    description: "Timeline marker of a restart",
  },
  historyTitle: {
    id: "tax.filing.events.title",
    defaultMessage: "Registration history",
    description: "Heading of the stop/restart list",
  },
  historyStop: {
    id: "tax.filing.events.stop",
    defaultMessage:
      "{date}: stopped — {reason}{hasNote, select, yes { — “{note}”} other {}} — {name}, {at}",
    description: "A stop in the history",
  },
  historyRestart: {
    id: "tax.filing.events.restart",
    defaultMessage:
      "{date}: restarted — {frequency}{hasNote, select, yes { — “{note}”} other {}} — {name}, {at}",
    description: "A restart in the history",
  },
  deregistration: {
    id: "tax.filing.reason.deregistration",
    defaultMessage: "Registration cancelled",
    description: "Stop reason",
  },
  small_supplier: {
    id: "tax.filing.reason.smallSupplier",
    defaultMessage: "Small supplier",
    description: "Stop reason",
  },
  suspension: {
    id: "tax.filing.reason.suspension",
    defaultMessage: "Suspended by the CRA or Revenu Québec",
    description: "Stop reason",
  },
  other: { id: "tax.filing.reason.other", defaultMessage: "Other", description: "Stop reason" },
});

export const reasonLabels: Record<StopReason, MessageDescriptor> = {
  deregistration: smsg.deregistration,
  small_supplier: smsg.small_supplier,
  suspension: smsg.suspension,
  other: smsg.other,
};
