import { defineMessages } from "@/i18n";

/** History preview panel (F-04-T13). */
export const preview = defineMessages({
  title: {
    id: "bankRules.preview.title",
    defaultMessage: "Test against history",
    description: "Heading of the preview panel",
  },
  intro: {
    id: "bankRules.preview.intro",
    defaultMessage:
      "What this rule would do to the uncoded lines of the last {days} days. Nothing is changed.",
    description: "Text of the preview panel",
  },
  refresh: {
    id: "bankRules.preview.refresh",
    defaultMessage: "Run the test",
    description: "Button",
  },
  running: {
    id: "bankRules.preview.running",
    defaultMessage: "Testing against your history…",
    description: "Status while the preview runs",
  },
  incomplete: {
    id: "bankRules.preview.incomplete",
    defaultMessage: "Complete the conditions to see which lines the rule matches.",
    description: "Preview hint before the conditions are complete",
  },
  summary: {
    id: "bankRules.preview.summary",
    defaultMessage:
      "{applies, plural, =0 {No line would be coded} one {# line would be coded} other {# lines would be coded}} by this rule; {shadowed, plural, =0 {none is taken by a higher rule} one {# is taken by a higher rule} other {# are taken by higher rules}}.",
    description: "Preview summary",
  },
  none: {
    id: "bankRules.preview.none",
    defaultMessage: "No uncoded line of the last {days} days matches this rule.",
    description: "Preview with no match",
  },
  failed: {
    id: "bankRules.preview.failed",
    defaultMessage: "The test couldn't run.",
    description: "Preview error",
  },
  truncated: {
    id: "bankRules.preview.truncated",
    defaultMessage: "Only the first 500 lines are listed.",
    description: "Preview list cut",
  },
  date: { id: "bankRules.preview.date", defaultMessage: "Date", description: "Column" },
  line: { id: "bankRules.preview.line", defaultMessage: "Statement line", description: "Column" },
  amount: { id: "bankRules.preview.amount", defaultMessage: "Amount", description: "Column" },
  outcome: { id: "bankRules.preview.outcome", defaultMessage: "Result", description: "Column" },
  applies: {
    id: "bankRules.preview.applies",
    defaultMessage: "Coded by this rule",
    description: "Outcome: the rule wins",
  },
  shadowedBy: {
    id: "bankRules.preview.shadowedBy",
    defaultMessage: "Shadowed by {name}",
    description: "Outcome: a higher-priority rule wins",
  },
  alsoMatches: {
    id: "bankRules.preview.alsoMatches",
    defaultMessage: "Also matches {names} (lower priority)",
    description: "Lower-priority rules this rule shadows on the line",
  },
});
