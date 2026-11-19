import { defineMessages } from "@/i18n";

export const tm = defineMessages({
  title: {
    id: "demo.tour.title",
    defaultMessage: "{title} ({step} of {total})",
    description: "Tour dialog title with the step",
  },
  next: { id: "demo.tour.next", defaultMessage: "Next", description: "Button" },
  back: { id: "demo.tour.back", defaultMessage: "Back", description: "Button" },
  skip: { id: "demo.tour.skip", defaultMessage: "Skip the tour", description: "Button" },
  done: { id: "demo.tour.done", defaultMessage: "Finish", description: "Button" },
  close: { id: "demo.tour.close", defaultMessage: "Close the tour", description: "Close button" },
  s1Title: { id: "demo.tour.s1.title", defaultMessage: "Welcome", description: "Step title" },
  s1Text: {
    id: "demo.tour.s1.text",
    defaultMessage:
      "This is Maple & Pine Supply Co., a sample Ontario retailer. Try anything — you can reset it at any time.",
    description: "Step text",
  },
  s2Title: { id: "demo.tour.s2.title", defaultMessage: "Contacts", description: "Step title" },
  s2Text: {
    id: "demo.tour.s2.text",
    defaultMessage:
      "25 customers and suppliers across six provinces, with people, addresses and Business Numbers.",
    description: "Step text",
  },
  s3Title: {
    id: "demo.tour.s3.title",
    defaultMessage: "Chart of accounts",
    description: "Step title",
  },
  s3Text: {
    id: "demo.tour.s3.text",
    defaultMessage:
      "The Canadian chart a new Ontario organisation gets, with GIFI codes and the opening balances already posted.",
    description: "Step text",
  },
  s4Title: { id: "demo.tour.s4.title", defaultMessage: "Statements", description: "Step title" },
  s4Text: {
    id: "demo.tour.s4.text",
    defaultMessage:
      "Open a customer, preview their statement and email it. In the demo, emails land in the Demo outbox instead.",
    description: "Step text",
  },
  s5Title: { id: "demo.tour.s5.title", defaultMessage: "Reset", description: "Step title" },
  s5Text: {
    id: "demo.tour.s5.text",
    defaultMessage: "Reset demo brings the sample data back exactly as it was.",
    description: "Step text",
  },
  s6Title: {
    id: "demo.tour.s6.title",
    defaultMessage: "Your own books",
    description: "Step title",
  },
  s6Text: {
    id: "demo.tour.s6.text",
    defaultMessage:
      "Ready? Start my free trial creates your own empty organisation with 30 days free.",
    description: "Step text",
  },
});
