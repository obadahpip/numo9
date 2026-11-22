import { defineMessages, type MessageDescriptor } from "@/i18n";

import type { TaxCodeType } from "./api";

export const m = defineMessages({
  title: { id: "tax.codes.title", defaultMessage: "Tax codes", description: "Page heading (G-01)" },
  intro: {
    id: "tax.codes.intro",
    defaultMessage:
      "Every rate is effective-dated: an ended rate can't be picked on a document dated after it.",
    description: "Text under the tax codes heading",
  },
  tabs: { id: "tax.codes.tabs", defaultMessage: "Side", description: "Tab list name" },
  sales: { id: "tax.codes.sales", defaultMessage: "Sales", description: "Tab" },
  purchases: { id: "tax.codes.purchases", defaultMessage: "Purchases", description: "Tab" },
  showExpired: {
    id: "tax.codes.showExpired",
    defaultMessage: "Show expired rates",
    description: "Toggle: also list ended code versions",
  },
  search: {
    id: "tax.codes.search",
    defaultMessage: "Search codes",
    description: "Search box label",
  },
  newCode: { id: "tax.codes.newCode", defaultMessage: "New tax code", description: "Button" },
  table: {
    id: "tax.codes.table",
    defaultMessage: "{side} tax codes",
    description: "Accessible name of the codes table",
  },
  colCode: { id: "tax.codes.colCode", defaultMessage: "Code", description: "Column" },
  colName: { id: "tax.codes.colName", defaultMessage: "Name", description: "Column" },
  colType: { id: "tax.codes.colType", defaultMessage: "Type", description: "Column" },
  colComponents: {
    id: "tax.codes.colComponents",
    defaultMessage: "Components",
    description: "Column",
  },
  colEffective: {
    id: "tax.codes.colEffective",
    defaultMessage: "In force",
    description: "Column: the version's effective range",
  },
  colUsage: { id: "tax.codes.colUsage", defaultMessage: "Used on", description: "Column" },
  usage: {
    id: "tax.codes.usage",
    defaultMessage: "{count, plural, =0 {Not used} one {# line} other {# lines}}",
    description: "How many posted journal lines used the code",
  },
  from: {
    id: "tax.codes.from",
    defaultMessage: "From {start}",
    description: "Open-ended effective range",
  },
  range: {
    id: "tax.codes.range",
    defaultMessage: "{start} – {end}",
    description: "Closed effective range",
  },
  expired: {
    id: "tax.codes.expired",
    defaultMessage: "Expired",
    description: "Badge of an ended version",
  },
  archived: {
    id: "tax.codes.archived",
    defaultMessage: "Archived",
    description: "Badge of an archived code",
  },
  version: {
    id: "tax.codes.version",
    defaultMessage: "version {version}",
    description: "Code version shown after the code",
  },
  claimable: {
    id: "tax.codes.claimable",
    defaultMessage: "{pct} % claimable",
    description: "Restricted ITC share of a purchase code",
  },
  noComponents: {
    id: "tax.codes.noComponents",
    defaultMessage: "No tax",
    description: "Components cell of an exempt / out-of-scope code",
  },
  empty: {
    id: "tax.codes.empty",
    defaultMessage: "No code matches",
    description: "Empty state title",
  },
  loading: {
    id: "tax.codes.loading",
    defaultMessage: "Loading tax codes…",
    description: "Screen-reader text while the codes load",
  },
  loadFailed: {
    id: "tax.codes.loadFailed",
    defaultMessage: "Tax codes couldn't be loaded",
    description: "Error title",
  },
  loadFailedBody: {
    id: "tax.codes.loadFailedBody",
    defaultMessage: "Verify your connection and try again.",
    description: "Error body",
  },
  retry: { id: "tax.codes.retry", defaultMessage: "Try again", description: "Retry button" },
  edit: {
    id: "tax.codes.edit",
    defaultMessage: "Edit {name}",
    description: "Accessible name of a row's edit link",
  },
});

export const typeLabels: Record<TaxCodeType, MessageDescriptor> = defineMessages({
  taxable: { id: "tax.type.taxable", defaultMessage: "Taxable", description: "Tax code type" },
  zero_rated: {
    id: "tax.type.zeroRated",
    defaultMessage: "Zero-rated",
    description: "Tax code type",
  },
  exempt: { id: "tax.type.exempt", defaultMessage: "Exempt", description: "Tax code type" },
  out_of_scope: {
    id: "tax.type.outOfScope",
    defaultMessage: "Out of scope",
    description: "Tax code type",
  },
});
