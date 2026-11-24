import { defineMessages } from "@/i18n";

/** Credit-limit banners in the invoice editor (D-03a-T16). */
export const cm = defineMessages({
  warnTitle: {
    id: "sales.credit.warnTitle",
    defaultMessage: "Over the credit limit",
    description: "Banner heading: the customer goes over its credit limit (warn mode)",
  },
  warnBody: {
    id: "sales.credit.warnBody",
    defaultMessage: "You can still approve this invoice.",
    description: "Banner text in warn mode",
  },
  blockTitle: {
    id: "sales.credit.blockTitle",
    defaultMessage: "Credit limit reached",
    description: "Banner heading: the invoice can't be approved (block mode)",
  },
  blockBody: {
    id: "sales.credit.blockBody",
    defaultMessage: "This invoice can't be approved unless an override is approved for it.",
    description: "Banner text in block mode",
  },
  overrideTitle: {
    id: "sales.credit.overrideTitle",
    defaultMessage: "Override approved",
    description: "Banner heading: an approved override covers the invoice",
  },
  overrideBody: {
    id: "sales.credit.overrideBody",
    defaultMessage: "An approved override covers this invoice; it's used when you approve it.",
    description: "Banner text",
  },
  pending: {
    id: "sales.credit.pending",
    defaultMessage: "Override requested {date}: waiting for approval.",
    description: "An override request is waiting",
  },
  request: {
    id: "sales.credit.request",
    defaultMessage: "Request override",
    description: "Button",
  },
  dialogTitle: {
    id: "sales.credit.dialogTitle",
    defaultMessage: "Request a credit limit override",
    description: "Dialog heading",
  },
  dialogBody: {
    id: "sales.credit.dialogBody",
    defaultMessage:
      "{contact} would owe {projected}, {over} over the limit of {limit}. The people who approve overrides are notified.",
    description: "Dialog text",
  },
  reason: { id: "sales.credit.reason", defaultMessage: "Reason", description: "Field" },
  reasonRequired: {
    id: "sales.credit.reasonRequired",
    defaultMessage: "Say why the sale should go ahead over the credit limit.",
    description: "Field error",
  },
  send: { id: "sales.credit.send", defaultMessage: "Send request", description: "Button" },
  cancel: { id: "sales.credit.cancel", defaultMessage: "Cancel", description: "Button" },
  requested: {
    id: "sales.credit.requested",
    defaultMessage: "Override requested.",
    description: "Confirmation",
  },
  failed: {
    id: "sales.credit.failed",
    defaultMessage: "The request wasn't sent: {reason}",
    description: "Error",
  },
});
