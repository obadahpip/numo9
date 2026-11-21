import { defineMessages } from "@/i18n";

export const g = defineMessages({
  title: {
    id: "console.grants.title",
    defaultMessage: "Product grants",
    description: "Section on the console organisation page (U-03-T14)",
  },
  intro: {
    id: "console.grants.intro",
    defaultMessage:
      "Give this organisation a product for a few days, whatever its package — for a pilot or a support case. Each grant and removal is in the organisation's audit log with your reason.",
    description: "Section text",
  },
  product: { id: "console.grants.product", defaultMessage: "Product", description: "Field" },
  chooseProduct: {
    id: "console.grants.chooseProduct",
    defaultMessage: "Choose a product",
    description: "Select placeholder",
  },
  days: { id: "console.grants.days", defaultMessage: "Days", description: "Field" },
  daysHint: {
    id: "console.grants.daysHint",
    defaultMessage: "1 to {max, number} days from now.",
    description: "Field hint",
  },
  reason: { id: "console.grants.reason", defaultMessage: "Reason", description: "Field" },
  reasonHint: {
    id: "console.grants.reasonHint",
    defaultMessage: "Shown in the audit log, e.g. 'Payroll pilot agreed with the owner'.",
    description: "Field hint",
  },
  grant: { id: "console.grants.grant", defaultMessage: "Grant product", description: "Button" },
  granted: {
    id: "console.grants.granted",
    defaultMessage: "{product} granted until {date}.",
    description: "Status after granting",
  },
  invalidProduct: {
    id: "console.grants.invalidProduct",
    defaultMessage: "Choose a product.",
    description: "Validation",
  },
  invalidDays: {
    id: "console.grants.invalidDays",
    defaultMessage: "Enter a number of days from 1 to {max, number}.",
    description: "Validation",
  },
  invalidReason: {
    id: "console.grants.invalidReason",
    defaultMessage: "Enter a reason of at least 5 characters.",
    description: "Validation",
  },
  failed: {
    id: "console.grants.failed",
    defaultMessage: "The change wasn't saved. Try again.",
    description: "Error",
  },
  forbidden: {
    id: "console.grants.forbidden",
    defaultMessage: "Only platform owners can grant or remove products.",
    description: "Refused (403)",
  },
  none: {
    id: "console.grants.none",
    defaultMessage: "No product granted to this organisation.",
    description: "Empty list",
  },
  line: {
    id: "console.grants.line",
    defaultMessage: "{product} until {date} — {reason} ({by})",
    description: "One grant",
  },
  stateActive: {
    id: "console.grants.stateActive",
    defaultMessage: "Active",
    description: "Grant state",
  },
  stateExpired: {
    id: "console.grants.stateExpired",
    defaultMessage: "Ended",
    description: "Grant state",
  },
  stateRemoved: {
    id: "console.grants.stateRemoved",
    defaultMessage: "Removed",
    description: "Grant state",
  },
  remove: { id: "console.grants.remove", defaultMessage: "Remove", description: "Button" },
  removeLabel: {
    id: "console.grants.removeLabel",
    defaultMessage: "Remove {product}",
    description: "Accessible name of the remove button",
  },
  removed: {
    id: "console.grants.removed",
    defaultMessage: "{product} removed.",
    description: "Status after removing",
  },
  loadFailed: {
    id: "console.grants.loadFailed",
    defaultMessage: "Product grants didn't load",
    description: "Error",
  },
  retry: { id: "console.grants.retry", defaultMessage: "Try again", description: "Button" },
});
