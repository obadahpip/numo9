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

/** Receive screen (E-01-T12). */
export const receive = defineMessages({
  title: {
    id: "purchases.po.receive.title",
    defaultMessage: "Receive goods: {number}",
    description: "Heading of the receive screen",
  },
  supplier: {
    id: "purchases.po.receive.supplier",
    defaultMessage: "From {supplier}",
    description: "Under the heading",
  },
  back: {
    id: "purchases.po.receive.back",
    defaultMessage: "Back to the purchase order",
    description: "Link",
  },
  table: {
    id: "purchases.po.receive.table",
    defaultMessage: "Lines to receive",
    description: "Accessible name of the table",
  },
  line: { id: "purchases.po.receive.line", defaultMessage: "Item", description: "Column" },
  ordered: { id: "purchases.po.receive.ordered", defaultMessage: "Ordered", description: "Column" },
  received: {
    id: "purchases.po.receive.received",
    defaultMessage: "Received",
    description: "Column: received before",
  },
  outstanding: {
    id: "purchases.po.receive.outstanding",
    defaultMessage: "Outstanding",
    description: "Column",
  },
  now: {
    id: "purchases.po.receive.now",
    defaultMessage: "Receiving now",
    description: "Column: the quantity received in this delivery",
  },
  nowFor: {
    id: "purchases.po.receive.nowFor",
    defaultMessage: "Receiving now: {line}",
    description: "Accessible name of a quantity input",
  },
  overLine: {
    id: "purchases.po.receive.overLine",
    defaultMessage: "{quantity} more than ordered",
    description: "Warning on a line received beyond what was ordered",
  },
  date: {
    id: "purchases.po.receive.date",
    defaultMessage: "Date received",
    description: "Field",
  },
  notes: {
    id: "purchases.po.receive.notes",
    defaultMessage: "Notes (packing slip, damage…)",
    description: "Field",
  },
  fillAll: {
    id: "purchases.po.receive.fillAll",
    defaultMessage: "Receive everything outstanding",
    description: "Button: fill every line with its outstanding quantity",
  },
  keyboardHint: {
    id: "purchases.po.receive.keyboardHint",
    defaultMessage: "Enter moves to the next line; a barcode scanner works the same way.",
    description: "Help above the table",
  },
  record: {
    id: "purchases.po.receive.record",
    defaultMessage: "Record receipt",
    description: "Button",
  },
  recording: {
    id: "purchases.po.receive.recording",
    defaultMessage: "Recording…",
    description: "Button while saving",
  },
  done: {
    id: "purchases.po.receive.done",
    defaultMessage:
      "Receipt recorded. {outstanding, plural, =0 {Nothing is outstanding.} one {# still outstanding.} other {# still outstanding.}}",
    description: "Status after a receipt",
  },
  overTitle: {
    id: "purchases.po.receive.overTitle",
    defaultMessage: "More than ordered",
    description: "Heading of the over-receipt warning",
  },
  overRow: {
    id: "purchases.po.receive.overRow",
    defaultMessage: "{line}: {received} received of {ordered} ordered (tolerance up to {allowed})",
    description: "A line received beyond the tolerance",
  },
  confirmOver: {
    id: "purchases.po.receive.confirmOver",
    defaultMessage: "Receive anyway",
    description: "Button: confirm an over-receipt",
  },
  nothing: {
    id: "purchases.po.receive.nothing",
    defaultMessage: "Enter the quantity received on at least one line.",
    description: "Error",
  },
  notReceivable: {
    id: "purchases.po.receive.notReceivable",
    defaultMessage: "{status}: this purchase order can't be received.",
    description: "Banner",
  },
});

/** Purchase order list (E-01-T13). */
export const list = defineMessages({
  title: {
    id: "purchases.po.list.title",
    defaultMessage: "Purchase orders",
    description: "Heading",
  },
  tabs: {
    id: "purchases.po.list.tabs",
    defaultMessage: "Purchase orders by status",
    description: "Accessible name of the tab list",
  },
  all: { id: "purchases.po.list.all", defaultMessage: "All", description: "Tab" },
  newOrder: {
    id: "purchases.po.list.new",
    defaultMessage: "New purchase order",
    description: "Link",
  },
  commitments: {
    id: "purchases.po.list.commitments",
    defaultMessage: "Commitments",
    description: "Link to the commitment report",
  },
  search: {
    id: "purchases.po.list.search",
    defaultMessage: "Search by number, reference or supplier",
    description: "Search field",
  },
  number: { id: "purchases.po.list.number", defaultMessage: "Number", description: "Column" },
  supplier: { id: "purchases.po.list.supplier", defaultMessage: "Supplier", description: "Column" },
  date: { id: "purchases.po.list.date", defaultMessage: "Date", description: "Column" },
  delivery: {
    id: "purchases.po.list.delivery",
    defaultMessage: "Delivery",
    description: "Column: delivery date",
  },
  total: { id: "purchases.po.list.total", defaultMessage: "Total", description: "Column" },
  status: { id: "purchases.po.list.status", defaultMessage: "Status", description: "Column" },
  actions: { id: "purchases.po.list.actions", defaultMessage: "Actions", description: "Column" },
  draft: {
    id: "purchases.po.list.draftNumber",
    defaultMessage: "Draft",
    description: "Number cell of a PO without a number",
  },
  receive: {
    id: "purchases.po.list.receive",
    defaultMessage: "Receive {number}",
    description: "Row action",
  },
  createBill: {
    id: "purchases.po.list.createBill",
    defaultMessage: "Create bill from {number}",
    description: "Row action",
  },
  empty: {
    id: "purchases.po.list.empty",
    defaultMessage: "No purchase orders here.",
    description: "Empty tab",
  },
  loadFailed: {
    id: "purchases.po.list.loadFailed",
    defaultMessage: "The purchase orders couldn't be loaded",
    description: "Error title",
  },
  retry: { id: "purchases.po.list.retry", defaultMessage: "Try again", description: "Button" },
  billFailed: {
    id: "purchases.po.list.billFailed",
    defaultMessage: "The bill couldn't be created.",
    description: "Error",
  },
  more: {
    id: "purchases.po.list.more",
    defaultMessage: "Page {page} of {pages}",
    description: "Pagination",
  },
  next: { id: "purchases.po.list.next", defaultMessage: "Next page", description: "Button" },
  previous: {
    id: "purchases.po.list.previous",
    defaultMessage: "Previous page",
    description: "Button",
  },
});

/** Commitment report (E-01-T14). */
export const commitments = defineMessages({
  title: {
    id: "purchases.po.commitments.title",
    defaultMessage: "Commitments",
    description: "Heading of the commitment report",
  },
  intro: {
    id: "purchases.po.commitments.intro",
    defaultMessage:
      "What is ordered on approved purchase orders and not billed yet, before tax. Drafts and orders awaiting approval commit nothing.",
    description: "Under the heading",
  },
  by: { id: "purchases.po.commitments.by", defaultMessage: "Group by", description: "Field" },
  byAccount: {
    id: "purchases.po.commitments.byAccount",
    defaultMessage: "Account",
    description: "Option and column",
  },
  bySupplier: {
    id: "purchases.po.commitments.bySupplier",
    defaultMessage: "Supplier",
    description: "Option and column",
  },
  byMonth: {
    id: "purchases.po.commitments.byMonth",
    defaultMessage: "Month",
    description: "Option and column",
  },
  from: {
    id: "purchases.po.commitments.from",
    defaultMessage: "PO date from",
    description: "Field",
  },
  to: { id: "purchases.po.commitments.to", defaultMessage: "PO date to", description: "Field" },
  orders: {
    id: "purchases.po.commitments.orders",
    defaultMessage: "Open POs",
    description: "Column",
  },
  lines: {
    id: "purchases.po.commitments.lines",
    defaultMessage: "Open lines",
    description: "Column",
  },
  amount: {
    id: "purchases.po.commitments.amount",
    defaultMessage: "Open value",
    description: "Column",
  },
  budget: {
    id: "purchases.po.commitments.budget",
    defaultMessage: "Budget",
    description: "Column",
  },
  budgetLater: {
    id: "purchases.po.commitments.budgetLater",
    defaultMessage: "Budgets come with budgeting (K-04).",
    description: "Note under the table: the budget column is empty for now",
  },
  noAccount: {
    id: "purchases.po.commitments.noAccount",
    defaultMessage: "No account",
    description: "Row of lines without an account",
  },
  total: { id: "purchases.po.commitments.total", defaultMessage: "Total", description: "Row" },
  empty: {
    id: "purchases.po.commitments.empty",
    defaultMessage: "Nothing is committed for these dates.",
    description: "Empty report",
  },
  exportCsv: {
    id: "purchases.po.commitments.exportCsv",
    defaultMessage: "Export CSV",
    description: "Download link",
  },
  exportXlsx: {
    id: "purchases.po.commitments.exportXlsx",
    defaultMessage: "Export Excel",
    description: "Download link",
  },
  loadFailed: {
    id: "purchases.po.commitments.loadFailed",
    defaultMessage: "The commitment report couldn't be loaded",
    description: "Error title",
  },
  retry: {
    id: "purchases.po.commitments.retry",
    defaultMessage: "Try again",
    description: "Button",
  },
  back: {
    id: "purchases.po.commitments.back",
    defaultMessage: "Purchase orders",
    description: "Link back to the list",
  },
});
