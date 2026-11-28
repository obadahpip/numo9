import { defineMessages } from "@/i18n";

/** Rule builder (F-04-T11…T14). */
export const builder = defineMessages({
  newTitle: {
    id: "bankRules.builder.newTitle",
    defaultMessage: "New bank rule",
    description: "Heading",
  },
  editTitle: {
    id: "bankRules.builder.editTitle",
    defaultMessage: "Edit {name}",
    description: "Heading when editing a rule",
  },
  name: { id: "bankRules.builder.name", defaultMessage: "Rule name", description: "Field" },
  type: { id: "bankRules.builder.type", defaultMessage: "Rule type", description: "Field" },
  typeFixed: {
    id: "bankRules.builder.typeFixed",
    defaultMessage: "The type of a saved rule can't change.",
    description: "Hint under the disabled type field",
  },
  conditionsLegend: {
    id: "bankRules.builder.conditionsLegend",
    defaultMessage: "Conditions",
    description: "Legend of the conditions",
  },
  when: { id: "bankRules.builder.when", defaultMessage: "When", description: "Sentence start" },
  matchMode: {
    id: "bankRules.builder.matchMode",
    defaultMessage: "Match all or any condition",
    description: "Accessible name of the all/any select",
  },
  matchAll: {
    id: "bankRules.builder.matchAll",
    defaultMessage: "all",
    description: "When all of these…",
  },
  matchAny: {
    id: "bankRules.builder.matchAny",
    defaultMessage: "any",
    description: "When any of these…",
  },
  ofThese: {
    id: "bankRules.builder.ofThese",
    defaultMessage: "of these are true:",
    description: "Sentence: When all of these are true:",
  },
  fieldLabel: {
    id: "bankRules.builder.fieldLabel",
    defaultMessage: "Condition {number}: field",
    description: "Accessible name of a condition's field select",
  },
  operatorLabel: {
    id: "bankRules.builder.operatorLabel",
    defaultMessage: "Condition {number}: comparison",
    description: "Accessible name of a condition's operator select",
  },
  valueLabel: {
    id: "bankRules.builder.valueLabel",
    defaultMessage: "Condition {number}: value",
    description: "Accessible name of a condition's value",
  },
  patternLabel: {
    id: "bankRules.builder.patternLabel",
    defaultMessage: "Condition {number}: pattern",
    description: "Accessible name of a regex pattern field",
  },
  amountFrom: {
    id: "bankRules.builder.amountFrom",
    defaultMessage: "Condition {number}: lowest amount",
    description: "Amount between: first field",
  },
  amountTo: {
    id: "bankRules.builder.amountTo",
    defaultMessage: "Condition {number}: highest amount",
    description: "Amount between: second field",
  },
  amountHint: {
    id: "bankRules.builder.amountHint",
    defaultMessage: "Amounts are compared without their sign; both limits are included.",
    description: "Hint under an amount condition",
  },
  addCondition: {
    id: "bankRules.builder.addCondition",
    defaultMessage: "Add a condition",
    description: "Button",
  },
  removeCondition: {
    id: "bankRules.builder.removeCondition",
    defaultMessage: "Remove condition {number}",
    description: "Button",
  },
  sampleLabel: {
    id: "bankRules.builder.sampleLabel",
    defaultMessage: "Test condition {number} on a sample text",
    description: "Regex tester: sample text field",
  },
  samplePlaceholder: {
    id: "bankRules.builder.samplePlaceholder",
    defaultMessage: "Paste a statement description, e.g. PETRO-CANADA #1234",
    description: "Regex tester placeholder",
  },
  matchCount: {
    id: "bankRules.builder.matchCount",
    defaultMessage: "{count, plural, =0 {No match} one {# match} other {# matches}}",
    description: "Regex tester: number of matches",
  },
  patternInvalid: {
    id: "bankRules.builder.patternInvalid",
    defaultMessage: "This pattern isn't valid.",
    description: "Regex tester error",
  },
  regexHint: {
    id: "bankRules.builder.regexHint",
    defaultMessage:
      "Case and accents are ignored. Patterns that take too long to run are refused when you save.",
    description: "Regex tester hint",
  },
  options: {
    id: "bankRules.builder.options",
    defaultMessage: "Then",
    description: "Section heading: what the rule does",
  },
  contactStrategy: {
    id: "bankRules.builder.contactStrategy",
    defaultMessage: "Contact",
    description: "Field",
  },
  contactNone: {
    id: "bankRules.builder.contactNone",
    defaultMessage: "No contact",
    description: "Option",
  },
  contactFixed: {
    id: "bankRules.builder.contactFixed",
    defaultMessage: "Set this contact",
    description: "Option",
  },
  contactPayee: {
    id: "bankRules.builder.contactPayee",
    defaultMessage: "The contact named like the payee",
    description: "Option",
  },
  contactPick: {
    id: "bankRules.builder.contactPick",
    defaultMessage: "Contact to set",
    description: "Field",
  },
  reference: {
    id: "bankRules.builder.reference",
    defaultMessage: "Reference",
    description: "Field: reference template",
  },
  referenceHint: {
    id: "bankRules.builder.referenceHint",
    defaultMessage: "You can use {tokens}.",
    description: "Hint: placeholders of the reference template",
  },
  transferAccount: {
    id: "bankRules.builder.transferAccount",
    defaultMessage: "Other bank account",
    description: "Field of a transfer rule",
  },
  scope: { id: "bankRules.builder.scope", defaultMessage: "Bank accounts", description: "Legend" },
  scopeHint: {
    id: "bankRules.builder.scopeHint",
    defaultMessage: "None selected: the rule runs on every bank account.",
    description: "Hint of the scope checkboxes",
  },
  autoApply: {
    id: "bankRules.builder.autoApply",
    defaultMessage: "Auto-apply (code without review)",
    description: "Switch",
  },
  autoApplyHint: {
    id: "bankRules.builder.autoApplyHint",
    defaultMessage:
      "Lines are posted at once and marked auto-coded; you can review and revert them.",
    description: "Switch description",
  },
  active: { id: "bankRules.builder.active", defaultMessage: "Rule on", description: "Switch" },
  save: { id: "bankRules.builder.save", defaultMessage: "Save rule", description: "Button" },
  saving: {
    id: "bankRules.builder.saving",
    defaultMessage: "Saving…",
    description: "Button while saving",
  },
  cancel: { id: "bankRules.builder.cancel", defaultMessage: "Cancel", description: "Link" },
  saved: { id: "bankRules.builder.saved", defaultMessage: "Rule saved.", description: "Status" },
  saveFailed: {
    id: "bankRules.builder.saveFailed",
    defaultMessage: "The rule couldn't be saved.",
    description: "Error title",
  },
  incomplete: {
    id: "bankRules.builder.incomplete",
    defaultMessage: "Give the rule a name and complete every condition to save it.",
    description: "Why Save is disabled",
  },
  loadFailed: {
    id: "bankRules.builder.loadFailed",
    defaultMessage: "This rule couldn't be loaded.",
    description: "Error",
  },
});
