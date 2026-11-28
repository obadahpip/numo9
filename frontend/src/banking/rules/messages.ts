import { defineMessages, type MessageDescriptor } from "@/i18n";

import type { ConditionField, ConditionOperator, RuleType } from "./api";

/** Bank rules (F-04): list, builder, allocation grid, preview, line actions. */
export const m = defineMessages({
  title: { id: "bankRules.title", defaultMessage: "Bank rules", description: "Page heading" },
  intro: {
    id: "bankRules.intro",
    defaultMessage:
      "Rules code statement lines for you. They run top to bottom and the first rule that matches wins — drag a rule to change its priority.",
    description: "Text under the bank rules heading",
  },
  newRule: { id: "bankRules.newRule", defaultMessage: "New rule", description: "Link button" },
  search: {
    id: "bankRules.search",
    defaultMessage: "Search rules",
    description: "Label of the search box of the rules list",
  },
  searchHint: {
    id: "bankRules.searchHint",
    defaultMessage: "Clear the search to change the order.",
    description: "Shown while a search filters the list: reordering is off",
  },
  typeTabs: {
    id: "bankRules.typeTabs",
    defaultMessage: "Rule type",
    description: "Accessible name of the type switcher",
  },
  priority: {
    id: "bankRules.priority",
    defaultMessage: "Priority {priority}",
    description: "Screen-reader text before the rule's position",
  },
  dragHandle: {
    id: "bankRules.dragHandle",
    defaultMessage: "Move {name}",
    description:
      "Drag handle of a rule; with the keyboard: Space to pick up, arrows to move, Space to drop",
  },
  dragInstructions: {
    id: "bankRules.dragInstructions",
    defaultMessage:
      "To move a rule with the keyboard, press Space on its handle, use the arrow keys, then press Space again.",
    description: "Screen-reader instructions for drag to reorder",
  },
  moved: {
    id: "bankRules.moved",
    defaultMessage: "{name} is now priority {priority}.",
    description: "Announcement after a rule was moved",
  },
  reorderFailed: {
    id: "bankRules.reorderFailed",
    defaultMessage: "The new order couldn't be saved. The previous order is back.",
    description: "Error after a failed reorder",
  },
  toggle: {
    id: "bankRules.toggle",
    defaultMessage: "{name} on",
    description: "Accessible name of the on/off switch of a rule",
  },
  toggleFailed: {
    id: "bankRules.toggleFailed",
    defaultMessage: "{name} couldn't be turned on or off. Try again.",
    description: "Error after a failed toggle",
  },
  applied: {
    id: "bankRules.applied",
    defaultMessage: "{count, plural, one {Applied # time} other {Applied # times}} · last {date}",
    description: "Counter of a rule: how many lines it coded and when it last ran",
  },
  neverApplied: {
    id: "bankRules.neverApplied",
    defaultMessage: "Not applied yet",
    description: "Counter of a rule that never coded a line",
  },
  autoApply: {
    id: "bankRules.autoApply",
    defaultMessage: "Auto-apply",
    description: "Badge: the rule codes lines without review",
  },
  off: { id: "bankRules.off", defaultMessage: "Off", description: "Badge of an inactive rule" },
  disabledWarning: {
    id: "bankRules.disabledWarning",
    defaultMessage: "Disabled: it uses an archived account. Edit the rule or restore the account.",
    description: "Warning on a rule referencing an archived account",
  },
  emptyTitle: {
    id: "bankRules.emptyTitle",
    defaultMessage: "No rules yet",
    description: "Empty state title",
  },
  emptyBody: {
    id: "bankRules.emptyBody",
    defaultMessage:
      "Create a rule such as “When the description contains PETRO, code it to Fuel” and test it against your history before turning it on.",
    description: "Empty state body",
  },
  noMatch: {
    id: "bankRules.noMatch",
    defaultMessage: "No rule matches “{search}”.",
    description: "Search returned nothing",
  },
  loading: {
    id: "bankRules.loading",
    defaultMessage: "Loading rules…",
    description: "Screen-reader text while rules load",
  },
  loadFailed: {
    id: "bankRules.loadFailed",
    defaultMessage: "Rules couldn't be loaded",
    description: "Error title",
  },
  loadFailedBody: {
    id: "bankRules.loadFailedBody",
    defaultMessage: "Verify your connection and try again. Nothing else is blocked.",
    description: "Error body",
  },
  retry: { id: "bankRules.retry", defaultMessage: "Try again", description: "Button" },
  and: { id: "bankRules.and", defaultMessage: "and", description: "Joins conditions (all)" },
  or: { id: "bankRules.or", defaultMessage: "or", description: "Joins conditions (any)" },
  back: {
    id: "bankRules.back",
    defaultMessage: "Back to bank rules",
    description: "Link back to the rules list",
  },
});

export const typeLabels: Record<RuleType, MessageDescriptor> = defineMessages({
  spend: { id: "bankRules.type.spend", defaultMessage: "Spend money", description: "Rule type" },
  receive: {
    id: "bankRules.type.receive",
    defaultMessage: "Receive money",
    description: "Rule type",
  },
  transfer: { id: "bankRules.type.transfer", defaultMessage: "Transfer", description: "Rule type" },
});

export const fieldLabels: Record<ConditionField, MessageDescriptor> = defineMessages({
  payee: { id: "bankRules.field.payee", defaultMessage: "Payee", description: "Condition field" },
  description: {
    id: "bankRules.field.description",
    defaultMessage: "Description",
    description: "Condition field",
  },
  reference: {
    id: "bankRules.field.reference",
    defaultMessage: "Reference",
    description: "Condition field",
  },
  any_text: {
    id: "bankRules.field.anyText",
    defaultMessage: "Any text",
    description: "Condition field: payee, description or reference",
  },
  amount: {
    id: "bankRules.field.amount",
    defaultMessage: "Amount",
    description: "Condition field",
  },
});

export const operatorLabels: Record<ConditionOperator, MessageDescriptor> = defineMessages({
  equals: { id: "bankRules.op.equals", defaultMessage: "is", description: "Operator" },
  contains: { id: "bankRules.op.contains", defaultMessage: "contains", description: "Operator" },
  not_contains: {
    id: "bankRules.op.notContains",
    defaultMessage: "does not contain",
    description: "Operator",
  },
  starts_with: {
    id: "bankRules.op.startsWith",
    defaultMessage: "starts with",
    description: "Operator",
  },
  ends_with: { id: "bankRules.op.endsWith", defaultMessage: "ends with", description: "Operator" },
  regex: {
    id: "bankRules.op.regex",
    defaultMessage: "matches the pattern",
    description: "Operator: regular expression",
  },
  is_blank: { id: "bankRules.op.isBlank", defaultMessage: "is blank", description: "Operator" },
  between: { id: "bankRules.op.between", defaultMessage: "is between", description: "Operator" },
  gt: { id: "bankRules.op.gt", defaultMessage: "is more than", description: "Operator" },
  lt: { id: "bankRules.op.lt", defaultMessage: "is less than", description: "Operator" },
});

export const sentence = defineMessages({
  condition: {
    id: "bankRules.sentence.condition",
    defaultMessage: "{field} {operator} “{value}”",
    description: "One condition in a sentence: Description contains “PETRO”",
  },
  conditionBlank: {
    id: "bankRules.sentence.conditionBlank",
    defaultMessage: "{field} {operator}",
    description: "A condition without a value: Reference is blank",
  },
  conditionRange: {
    id: "bankRules.sentence.conditionRange",
    defaultMessage: "{field} {operator} {low} and {high}",
    description: "Amount is between 20 and 200",
  },
});
