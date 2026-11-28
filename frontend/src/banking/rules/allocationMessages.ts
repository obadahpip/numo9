import { defineMessages } from "@/i18n";

/** Allocation grid (F-04-T12). */
export const allocation = defineMessages({
  title: {
    id: "bankRules.allocation.title",
    defaultMessage: "Code it to",
    description: "Heading of the allocation grid",
  },
  intro: {
    id: "bankRules.allocation.intro",
    defaultMessage:
      "Fixed amounts are taken first; the percentages share the rest and must total 100 %. Amounts include tax.",
    description: "Text above the allocation grid",
  },
  account: { id: "bankRules.allocation.account", defaultMessage: "Account", description: "Column" },
  description: {
    id: "bankRules.allocation.description",
    defaultMessage: "Description",
    description: "Column",
  },
  taxCode: { id: "bankRules.allocation.taxCode", defaultMessage: "Tax", description: "Column" },
  share: { id: "bankRules.allocation.share", defaultMessage: "Share", description: "Column" },
  value: { id: "bankRules.allocation.value", defaultMessage: "Value", description: "Column" },
  actions: { id: "bankRules.allocation.actions", defaultMessage: "Actions", description: "Column" },
  accountLabel: {
    id: "bankRules.allocation.accountLabel",
    defaultMessage: "Line {number}: account",
    description: "Accessible name",
  },
  descriptionLabel: {
    id: "bankRules.allocation.descriptionLabel",
    defaultMessage: "Line {number}: description",
    description: "Accessible name",
  },
  taxLabel: {
    id: "bankRules.allocation.taxLabel",
    defaultMessage: "Line {number}: tax code",
    description: "Accessible name",
  },
  shareLabel: {
    id: "bankRules.allocation.shareLabel",
    defaultMessage: "Line {number}: percentage or fixed amount",
    description: "Accessible name",
  },
  percentLabel: {
    id: "bankRules.allocation.percentLabel",
    defaultMessage: "Line {number}: percentage",
    description: "Accessible name",
  },
  amountLabel: {
    id: "bankRules.allocation.amountLabel",
    defaultMessage: "Line {number}: fixed amount",
    description: "Accessible name",
  },
  accountOption: {
    id: "bankRules.allocation.accountOption",
    defaultMessage: "{code} · {name}",
    description: "An account in the picker: code and name",
  },
  noTax: { id: "bankRules.allocation.noTax", defaultMessage: "No tax", description: "Option" },
  percent: {
    id: "bankRules.allocation.percent",
    defaultMessage: "Percentage",
    description: "Option",
  },
  fixed: {
    id: "bankRules.allocation.fixed",
    defaultMessage: "Fixed amount",
    description: "Option",
  },
  remove: {
    id: "bankRules.allocation.remove",
    defaultMessage: "Remove line {number}",
    description: "Button",
  },
  addLine: {
    id: "bankRules.allocation.addLine",
    defaultMessage: "Add a line",
    description: "Button",
  },
  totalOk: {
    id: "bankRules.allocation.totalOk",
    defaultMessage: "Total {total} % — ready",
    description: "Running total at exactly 100 %",
  },
  totalOff: {
    id: "bankRules.allocation.totalOff",
    defaultMessage: "Total {total} % — the percentages must total 100 %",
    description: "Running total not at 100 %",
  },
  totalInvalid: {
    id: "bankRules.allocation.totalInvalid",
    defaultMessage: "Enter each percentage as a number, e.g. 33.33",
    description: "A percentage is not a number",
  },
  fixedOnly: {
    id: "bankRules.allocation.fixedOnly",
    defaultMessage: "Fixed amounts only: the rule codes lines of exactly their total.",
    description: "Total line without percentages",
  },
  none: {
    id: "bankRules.allocation.none",
    defaultMessage: "Add at least one line.",
    description: "No allocation line",
  },
});
