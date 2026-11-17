import { defineMessages } from "@/i18n";

/** Impersonation modal and bar (U-06-T11). */
export const m = defineMessages({
  signInAs: {
    id: "console.impersonation.signInAs",
    defaultMessage: "Sign in as {name}",
    description: "Button on a user of an organisation in the console",
  },
  title: {
    id: "console.impersonation.title",
    defaultMessage: "Sign in as {name}",
    description: "Start dialog title",
  },
  description: {
    id: "console.impersonation.description",
    defaultMessage:
      "You'll see {organisation} as {name} sees it. Everything you do is recorded in the organisation's audit log under both names. Payment methods, billing changes, passwords, two-factor authentication and email addresses stay locked.",
    description: "Start dialog explanation",
  },
  reason: {
    id: "console.impersonation.reason",
    defaultMessage: "Reason",
    description: "Field label",
  },
  reasonHint: {
    id: "console.impersonation.reasonHint",
    defaultMessage: "For example the support ticket. The organisation's owner can read it.",
    description: "Field hint",
  },
  duration: {
    id: "console.impersonation.duration",
    defaultMessage: "Time limit",
    description: "Field label",
  },
  minutes: {
    id: "console.impersonation.minutes",
    defaultMessage: "{minutes, plural, one {# minute} other {# minutes}}",
    description: "Duration option",
  },
  hours: {
    id: "console.impersonation.hours",
    defaultMessage: "{hours, plural, one {# hour} other {# hours}}",
    description: "Duration option",
  },
  start: {
    id: "console.impersonation.start",
    defaultMessage: "Start session",
    description: "Dialog primary action",
  },
  cancel: { id: "console.impersonation.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "console.impersonation.close", defaultMessage: "Close", description: "Button" },
  failed: {
    id: "console.impersonation.failed",
    defaultMessage: "We couldn't start the session. Try again.",
    description: "Generic start error",
  },
  bar: {
    id: "console.impersonation.bar",
    defaultMessage: "You're signed in as {name} in {organisation}",
    description: "Red bar on every page while impersonating",
  },
  barLabel: {
    id: "console.impersonation.barLabel",
    defaultMessage: "Support session",
    description: "Accessible name of the impersonation bar",
  },
  remaining: {
    id: "console.impersonation.remaining",
    defaultMessage: "{time} left",
    description: "Countdown in the bar",
  },
  end: {
    id: "console.impersonation.end",
    defaultMessage: "End session",
    description: "Bar button",
  },
  endedTitle: {
    id: "console.impersonation.endedTitle",
    defaultMessage: "Your session as {name} has ended",
    description: "Bar after the time limit",
  },
  backToConsole: {
    id: "console.impersonation.backToConsole",
    defaultMessage: "Back to the console",
    description: "Link after a session ended",
  },
});
