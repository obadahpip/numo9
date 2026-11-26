import { defineMessages, type MessageDescriptor } from "@/i18n";

import type { PurchaseOrderStatus } from "./api";

/** Purchase order editor (E-01-T11). */
export const po = defineMessages({
  newTitle: {
    id: "purchases.po.newTitle",
    defaultMessage: "New purchase order",
    description: "Heading",
  },
  title: {
    id: "purchases.po.title",
    defaultMessage: "Purchase order {number}",
    description: "Heading of a numbered purchase order",
  },
  draftTitle: {
    id: "purchases.po.draftTitle",
    defaultMessage: "Draft purchase order",
    description: "Heading",
  },
  form: {
    id: "purchases.po.form",
    defaultMessage: "Purchase order details",
    description: "Form name",
  },
  supplier: { id: "purchases.po.supplier", defaultMessage: "Supplier", description: "Field" },
  chooseSupplier: {
    id: "purchases.po.chooseSupplier",
    defaultMessage: "Choose a supplier",
    description: "Empty option",
  },
  date: { id: "purchases.po.date", defaultMessage: "Order date", description: "Field" },
  reference: { id: "purchases.po.reference", defaultMessage: "Reference", description: "Field" },
  taxMode: { id: "purchases.po.taxMode", defaultMessage: "Amounts are", description: "Field" },
  taxExclusive: {
    id: "purchases.po.taxExclusive",
    defaultMessage: "Tax exclusive",
    description: "Option",
  },
  taxInclusive: {
    id: "purchases.po.taxInclusive",
    defaultMessage: "Tax inclusive",
    description: "Option",
  },
  taxNone: { id: "purchases.po.taxNone", defaultMessage: "No tax", description: "Option" },
  delivery: {
    id: "purchases.po.delivery",
    defaultMessage: "Delivery",
    description: "Delivery block heading",
  },
  deliveryAddress: {
    id: "purchases.po.deliveryAddress",
    defaultMessage: "Deliver to",
    description: "Field: delivery address",
  },
  deliveryAttention: {
    id: "purchases.po.deliveryAttention",
    defaultMessage: "Attention",
    description: "Field: person receiving the delivery",
  },
  deliveryDate: {
    id: "purchases.po.deliveryDate",
    defaultMessage: "Delivery date",
    description: "Field",
  },
  deliveryInstructions: {
    id: "purchases.po.deliveryInstructions",
    defaultMessage: "Instructions",
    description: "Field: delivery instructions",
  },
  notes: { id: "purchases.po.notes", defaultMessage: "Notes", description: "Field" },
  limitWithin: {
    id: "purchases.po.limitWithin",
    defaultMessage: "Within your approval limit of {limit}: you can approve it.",
    description: "Limit indicator: the total is within the person's PO approval limit",
  },
  limitAbove: {
    id: "purchases.po.limitAbove",
    defaultMessage: "{total} is above your approval limit of {limit}: it goes to an approver.",
    description: "Limit indicator: the total is above the person's PO approval limit",
  },
  limitNone: {
    id: "purchases.po.limitNone",
    defaultMessage: "You have no purchase order approval limit: it goes to an approver.",
    description: "Limit indicator: the person can't approve purchase orders",
  },
  limitTitle: {
    id: "purchases.po.limitTitle",
    defaultMessage: "Approval limit",
    description: "Accessible name of the limit indicator",
  },
  saveDraft: { id: "purchases.po.saveDraft", defaultMessage: "Save draft", description: "Button" },
  submit: {
    id: "purchases.po.submit",
    defaultMessage: "Submit for approval",
    description: "Button",
  },
  approve: { id: "purchases.po.approve", defaultMessage: "Approve", description: "Button" },
  saveChanges: {
    id: "purchases.po.saveChanges",
    defaultMessage: "Save changes",
    description: "Button on an approved purchase order",
  },
  saving: { id: "purchases.po.saving", defaultMessage: "Saving…", description: "Button" },
  saved: { id: "purchases.po.saved", defaultMessage: "Saved as a draft.", description: "Status" },
  changesSaved: {
    id: "purchases.po.changesSaved",
    defaultMessage: "Changes saved.",
    description: "Status",
  },
  reapproval: {
    id: "purchases.po.reapproval",
    defaultMessage: "The total went up: the purchase order is waiting for approval again.",
    description: "Status after an approved PO's total increased",
  },
  submitted: {
    id: "purchases.po.submitted",
    defaultMessage: "Submitted: it is waiting for approval.",
    description: "Status",
  },
  approved: {
    id: "purchases.po.approved",
    defaultMessage: "{number} is approved. Send it to the supplier.",
    description: "Status",
  },
  failed: {
    id: "purchases.po.failed",
    defaultMessage: "The purchase order couldn't be saved.",
    description: "Error",
  },
  loadFailed: {
    id: "purchases.po.loadFailed",
    defaultMessage: "The purchase order couldn't be loaded",
    description: "Error title",
  },
  retry: { id: "purchases.po.retry", defaultMessage: "Try again", description: "Button" },
  readOnly: {
    id: "purchases.po.readOnly",
    defaultMessage: "{status}: this purchase order can't be edited any more.",
    description: "Banner of a PO that can't be edited",
  },
  receive: {
    id: "purchases.po.receiveAction",
    defaultMessage: "Receive goods",
    description: "Link to the receive screen",
  },
  createBill: {
    id: "purchases.po.createBill",
    defaultMessage: "Create bill",
    description: "Button: bill what was received",
  },
  pdf: { id: "purchases.po.pdf", defaultMessage: "PDF", description: "Link: the PO's PDF" },
  cancel: {
    id: "purchases.po.cancel",
    defaultMessage: "Cancel order",
    description: "Button: cancel the PO",
  },
  close: {
    id: "purchases.po.close",
    defaultMessage: "Close order",
    description: "Button: close the PO, nothing more to receive",
  },
});

export const statusLabels: Record<PurchaseOrderStatus, MessageDescriptor> = defineMessages({
  draft: { id: "purchases.po.status.draft", defaultMessage: "Draft", description: "PO status" },
  awaiting_approval: {
    id: "purchases.po.status.awaitingApproval",
    defaultMessage: "Awaiting approval",
    description: "PO status",
  },
  approved: {
    id: "purchases.po.status.approved",
    defaultMessage: "Approved",
    description: "PO status",
  },
  partially_received: {
    id: "purchases.po.status.partiallyReceived",
    defaultMessage: "Partially received",
    description: "PO status",
  },
  received: {
    id: "purchases.po.status.received",
    defaultMessage: "Received",
    description: "PO status",
  },
  billed: { id: "purchases.po.status.billed", defaultMessage: "Billed", description: "PO status" },
  closed: { id: "purchases.po.status.closed", defaultMessage: "Closed", description: "PO status" },
  cancelled: {
    id: "purchases.po.status.cancelled",
    defaultMessage: "Cancelled",
    description: "PO status",
  },
});
