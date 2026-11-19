import { defineMessages } from "@/i18n";

export const dm = defineMessages({
  region: { id: "demo.bar.region", defaultMessage: "Demo organisation", description: "Bar region" },
  tag: { id: "demo.bar.tag", defaultMessage: "Demo", description: "Watermark tag on the bar" },
  text: {
    id: "demo.bar.text",
    defaultMessage:
      "You're exploring Maple & Pine Supply Co., a sample company. Nothing here is real and no email leaves Numo9.",
    description: "Demo bar explanation",
  },
  reset: { id: "demo.bar.reset", defaultMessage: "Reset demo", description: "Button" },
  trial: { id: "demo.bar.trial", defaultMessage: "Start my free trial", description: "Button" },
  outbox: {
    id: "demo.bar.outbox",
    defaultMessage: "Demo outbox",
    description: "Button that opens the emails the demo would have sent",
  },
  tour: { id: "demo.bar.tour", defaultMessage: "Take the tour", description: "Button" },
  resetTitle: {
    id: "demo.reset.title",
    defaultMessage: "Reset the demo?",
    description: "Dialog title",
  },
  resetText: {
    id: "demo.reset.text",
    defaultMessage:
      "Everything you added or changed goes away and the sample data comes back as it was.",
    description: "Dialog text",
  },
  resetConfirm: { id: "demo.reset.confirm", defaultMessage: "Reset", description: "Button" },
  cancel: { id: "demo.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "demo.close", defaultMessage: "Close", description: "Close button" },
  resetting: {
    id: "demo.reset.progress",
    defaultMessage: "Resetting the demo…",
    description: "Progress label",
  },
  resetDone: {
    id: "demo.reset.done",
    defaultMessage: "The demo is back to its sample data.",
    description: "Status after reset",
  },
  failed: {
    id: "demo.failed",
    defaultMessage: "That didn't work: {reason}",
    description: "Error",
  },
  trialTitle: {
    id: "demo.trial.title",
    defaultMessage: "Start your free trial",
    description: "Dialog title",
  },
  trialText: {
    id: "demo.trial.text",
    defaultMessage:
      "We create a new, empty organisation with a 30-day free trial. The sample data stays behind and the demo is deleted.",
    description: "Dialog text",
  },
  trialName: {
    id: "demo.trial.name",
    defaultMessage: "Your organisation's name",
    description: "Field",
  },
  trialConfirm: {
    id: "demo.trial.confirm",
    defaultMessage: "Start the trial",
    description: "Button",
  },
  signUpFirst: {
    id: "demo.trial.signUpFirst",
    defaultMessage: "Create your free account first.",
    description: "Link text when an anonymous visitor starts a trial",
  },
  outboxTitle: {
    id: "demo.outbox.title",
    defaultMessage: "Demo outbox",
    description: "Drawer title",
  },
  outboxText: {
    id: "demo.outbox.text",
    defaultMessage: "Emails this demo would have sent. They were kept here, never sent.",
    description: "Drawer description",
  },
  outboxEmpty: {
    id: "demo.outbox.empty",
    defaultMessage: "No email yet. Send a statement from a contact to see one here.",
    description: "Empty outbox",
  },
  outboxLine: {
    id: "demo.outbox.line",
    defaultMessage: "To {to} · {when}",
    description: "Outbox email meta line",
  },
});
