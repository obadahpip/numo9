import { defineMessages, type MessageDescriptor } from "@/i18n";

import type { BillTab } from "./api";

/** Purchases overview and the bills list tabs (E-02-T15). */
export const om = defineMessages({
  title: {
    id: "purchases.overview.title",
    defaultMessage: "Purchases overview",
    description: "Heading",
  },
  intro: {
    id: "purchases.overview.intro",
    defaultMessage: "Bills you've entered, what's waiting for approval and what you owe.",
    description: "Line under the heading",
  },
  newBill: { id: "purchases.overview.newBill", defaultMessage: "New bill", description: "Button" },
  allBills: {
    id: "purchases.overview.allBills",
    defaultMessage: "View all bills",
    description: "Link to the bills list",
  },
  tile: {
    id: "purchases.overview.tile",
    defaultMessage: "{label}: {count, plural, one {# bill} other {# bills}}, {amount}",
    description: "Accessible name of a status tile (count and amount)",
  },
  tilesCard: {
    id: "purchases.overview.tilesCard",
    defaultMessage: "Bills by status",
    description: "Name of the status tiles (in their error message)",
  },
  agingCard: {
    id: "purchases.overview.agingCard",
    defaultMessage: "Money going out",
    description: "Card heading: what is owed to suppliers by age",
  },
  agingChart: {
    id: "purchases.overview.agingChart",
    defaultMessage: "Money going out by age: {total} owed",
    description: "Accessible name of the aging bar",
  },
  agingEmpty: {
    id: "purchases.overview.agingEmpty",
    defaultMessage: "Nothing owed — every approved bill is paid.",
    description: "Aging bar with no open bill",
  },
  suppliersCard: {
    id: "purchases.overview.suppliersCard",
    defaultMessage: "Suppliers you owe the most",
    description: "Card heading",
  },
  suppliersEmpty: {
    id: "purchases.overview.suppliersEmpty",
    defaultMessage: "You don't owe any supplier right now.",
    description: "Empty top-suppliers card",
  },
  supplierOverdue: {
    id: "purchases.overview.supplierOverdue",
    defaultMessage: "{amount} overdue",
    description: "Under a supplier's balance",
  },
  supplierBills: {
    id: "purchases.overview.supplierBills",
    defaultMessage: "{count, plural, one {# open bill} other {# open bills}}",
    description: "Under a supplier's name",
  },
  asOf: {
    id: "purchases.overview.asOf",
    defaultMessage: "Overdue means due before {date}.",
    description: "Footnote: the organisation's today",
  },
  emptyTitle: {
    id: "purchases.overview.emptyTitle",
    defaultMessage: "No bills yet",
    description: "Empty organisation",
  },
  emptyBody: {
    id: "purchases.overview.emptyBody",
    defaultMessage:
      "Enter your first supplier bill, or forward a supplier's invoice to your documents inbox.",
    description: "Empty organisation",
  },
  // ---- bills list ----
  listTitle: { id: "purchases.bills.title", defaultMessage: "Bills", description: "Heading" },
  overviewLink: {
    id: "purchases.bills.overviewLink",
    defaultMessage: "Purchases overview",
    description: "Link back to the overview",
  },
  tabs: {
    id: "purchases.bills.tabs",
    defaultMessage: "Bills by status",
    description: "Accessible name of the list tabs",
  },
  grid: { id: "purchases.bills.grid", defaultMessage: "Bills", description: "Grid name" },
  search: {
    id: "purchases.bills.search",
    defaultMessage: "Search number, supplier or supplier invoice no.",
    description: "Search box",
  },
  colNumber: { id: "purchases.bills.colNumber", defaultMessage: "Number", description: "Column" },
  colSupplier: {
    id: "purchases.bills.colSupplier",
    defaultMessage: "Supplier",
    description: "Column",
  },
  colSupplierInvoice: {
    id: "purchases.bills.colSupplierInvoice",
    defaultMessage: "Supplier invoice no.",
    description: "Column",
  },
  colDate: { id: "purchases.bills.colDate", defaultMessage: "Date", description: "Column" },
  colDue: { id: "purchases.bills.colDue", defaultMessage: "Due date", description: "Column" },
  colStatus: { id: "purchases.bills.colStatus", defaultMessage: "Status", description: "Column" },
  colTotal: { id: "purchases.bills.colTotal", defaultMessage: "Total", description: "Column" },
  colDueAmount: {
    id: "purchases.bills.colDueAmount",
    defaultMessage: "Amount due",
    description: "Column",
  },
  draftNumber: {
    id: "purchases.bills.draftNumber",
    defaultMessage: "Draft",
    description: "Number cell of a draft (no number yet)",
  },
  failed: {
    id: "purchases.bills.failed",
    defaultMessage: "Bills couldn't be loaded",
    description: "Error title",
  },
  retry: { id: "purchases.bills.retry", defaultMessage: "Try again", description: "Button" },
  empty: {
    id: "purchases.bills.empty",
    defaultMessage: "No bills here",
    description: "Empty tab",
  },
  tabEmptyBody: {
    id: "purchases.bills.emptyBody",
    defaultMessage: "Bills with this status appear here.",
    description: "Empty tab",
  },
  noResults: {
    id: "purchases.bills.noResults",
    defaultMessage: "No bill matches your search",
    description: "Search without result",
  },
  results: {
    id: "purchases.bills.results",
    defaultMessage: "{shown, plural, one {# bill} other {# bills}} of {total}",
    description: "Grid live region",
  },
  loading: {
    id: "purchases.bills.loading",
    defaultMessage: "Loading bills…",
    description: "Grid loading",
  },
  previous: {
    id: "purchases.bills.previous",
    defaultMessage: "Previous page",
    description: "Pager",
  },
  next: { id: "purchases.bills.next", defaultMessage: "Next page", description: "Pager" },
  pageOf: {
    id: "purchases.bills.pageOf",
    defaultMessage: "Page {page} of {pages}",
    description: "Pager",
  },
});

export const TAB_LABEL: Record<BillTab, MessageDescriptor> = defineMessages({
  all: { id: "purchases.bills.tab.all", defaultMessage: "All", description: "Bills list tab" },
  draft: {
    id: "purchases.bills.tab.draft",
    defaultMessage: "Draft",
    description: "Bills list tab",
  },
  awaiting_approval: {
    id: "purchases.bills.tab.awaitingApproval",
    defaultMessage: "Awaiting approval",
    description: "Bills list tab",
  },
  awaiting_payment: {
    id: "purchases.bills.tab.awaitingPayment",
    defaultMessage: "Awaiting payment",
    description: "Bills list tab (includes partially paid)",
  },
  overdue: {
    id: "purchases.bills.tab.overdue",
    defaultMessage: "Overdue",
    description: "Bills list tab",
  },
  paid: { id: "purchases.bills.tab.paid", defaultMessage: "Paid", description: "Bills list tab" },
  void: { id: "purchases.bills.tab.void", defaultMessage: "Void", description: "Bills list tab" },
});

export const AGING_LABEL: Record<string, MessageDescriptor> = defineMessages({
  current: {
    id: "purchases.overview.aging.current",
    defaultMessage: "Current",
    description: "Aging bucket: not due yet",
  },
  "1_30": {
    id: "purchases.overview.aging.days1to30",
    defaultMessage: "1–30 days",
    description: "Aging bucket: days past due",
  },
  "31_60": {
    id: "purchases.overview.aging.days31to60",
    defaultMessage: "31–60 days",
    description: "Aging bucket",
  },
  "61_90": {
    id: "purchases.overview.aging.days61to90",
    defaultMessage: "61–90 days",
    description: "Aging bucket",
  },
  over_90: {
    id: "purchases.overview.aging.over90",
    defaultMessage: "Over 90 days",
    description: "Aging bucket",
  },
});
