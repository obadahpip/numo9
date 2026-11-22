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

export const ed = defineMessages({
  newTitle: { id: "tax.editor.newTitle", defaultMessage: "New tax code", description: "Heading" },
  editTitle: {
    id: "tax.editor.editTitle",
    defaultMessage: "Edit tax code — {name}",
    description: "Heading",
  },
  back: { id: "tax.editor.back", defaultMessage: "Tax codes", description: "Breadcrumb link" },
  code: { id: "tax.editor.code", defaultMessage: "Code", description: "Field label" },
  codeHint: {
    id: "tax.editor.codeHint",
    defaultMessage: "A stable key, e.g. purchase.ON.fuel",
    description: "Hint under the code field",
  },
  name: { id: "tax.editor.name", defaultMessage: "Name", description: "Field label" },
  side: { id: "tax.editor.side", defaultMessage: "Side", description: "Field label" },
  type: { id: "tax.editor.type", defaultMessage: "Type", description: "Field label" },
  province: {
    id: "tax.editor.province",
    defaultMessage: "Province or territory",
    description: "Field label",
  },
  anywhere: {
    id: "tax.editor.anywhere",
    defaultMessage: "Anywhere",
    description: "Province option: the code isn't for one province",
  },
  effectiveFrom: {
    id: "tax.editor.effectiveFrom",
    defaultMessage: "Effective from",
    description: "Field label",
  },
  newVersionHint: {
    id: "tax.editor.newVersionHint",
    defaultMessage:
      "Saving creates version {version} from this date; posted lines keep version {current}.",
    description: "Hint under the date when editing an existing code",
  },
  claimable: {
    id: "tax.editor.claimable",
    defaultMessage: "Claimable ITC % (optional)",
    description: "Field label: restricted ITC share of a purchase code",
  },
  components: {
    id: "tax.editor.components",
    defaultMessage: "Components",
    description: "Section heading",
  },
  component: {
    id: "tax.editor.component",
    defaultMessage: "Component {n}",
    description: "Accessible name of a component picker",
  },
  pickComponent: {
    id: "tax.editor.pickComponent",
    defaultMessage: "Choose a component",
    description: "Empty option of a component picker",
  },
  recoverable: {
    id: "tax.editor.recoverable",
    defaultMessage: "Recoverable % for component {n}",
    description: "Accessible name of the recoverable % input",
  },
  remove: {
    id: "tax.editor.remove",
    defaultMessage: "Remove component {n}",
    description: "Button",
  },
  add: { id: "tax.editor.add", defaultMessage: "Add component", description: "Button" },
  example: {
    id: "tax.editor.example",
    defaultMessage: "Live example",
    description: "Panel heading",
  },
  exampleAmount: {
    id: "tax.editor.exampleAmount",
    defaultMessage: "Amount",
    description: "Example amount label",
  },
  exampleInclusive: {
    id: "tax.editor.exampleInclusive",
    defaultMessage: "Amount includes tax",
    description: "Example toggle",
  },
  exampleTotal: {
    id: "tax.editor.exampleTotal",
    defaultMessage: "Total",
    description: "Example line",
  },
  exampleNet: {
    id: "tax.editor.exampleNet",
    defaultMessage: "Before tax",
    description: "Example line",
  },
  exampleClaimable: {
    id: "tax.editor.exampleClaimable",
    defaultMessage: "Recoverable (ITC / ITR)",
    description: "Example line",
  },
  exampleCost: {
    id: "tax.editor.exampleCost",
    defaultMessage: "Added to the expense",
    description: "Example line",
  },
  save: { id: "tax.editor.save", defaultMessage: "Save", description: "Button" },
  saveVersion: {
    id: "tax.editor.saveVersion",
    defaultMessage: "Save as a new version",
    description: "Button when editing an existing code",
  },
  cancel: { id: "tax.editor.cancel", defaultMessage: "Cancel", description: "Link" },
  saved: {
    id: "tax.editor.saved",
    defaultMessage: "{name} saved (version {version}).",
    description: "Status after saving",
  },
  failed: {
    id: "tax.editor.failed",
    defaultMessage: "The tax code couldn't be saved.",
    description: "Generic error",
  },
  required: {
    id: "tax.editor.required",
    defaultMessage: "Fill in the code, name and date.",
    description: "Validation message",
  },
  componentOption: {
    id: "tax.editor.componentOption",
    defaultMessage: "{name} {rate} % · {authority}",
    description: "A component in the picker: name, rate and authority",
  },
  componentRate: {
    id: "tax.editor.componentRate",
    defaultMessage: "{name} {rate} %",
    description: "A component line of the live example",
  },
  recoverablePlaceholder: {
    id: "tax.editor.recoverablePlaceholder",
    defaultMessage: "100",
    description: "Placeholder of the recoverable % input (full recovery)",
  },
});
