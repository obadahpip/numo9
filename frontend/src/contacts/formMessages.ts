import { defineMessages } from "@/i18n";

/** Contact form (B-01-T15) and merge dialog (B-01-T17). */
export const fmsg = defineMessages({
  newTitle: { id: "contacts.form.newTitle", defaultMessage: "New contact", description: "Heading" },
  sections: { id: "contacts.form.sections", defaultMessage: "Sections", description: "Nav name" },
  details: { id: "contacts.form.details", defaultMessage: "Details", description: "Section" },
  people: { id: "contacts.form.people", defaultMessage: "People", description: "Section" },
  addresses: { id: "contacts.form.addresses", defaultMessage: "Addresses", description: "Section" },
  financial: { id: "contacts.form.financial", defaultMessage: "Financial", description: "Section" },
  defaults: {
    id: "contacts.form.defaults",
    defaultMessage: "Sales and purchase defaults",
    description: "Section",
  },
  displayName: {
    id: "contacts.form.displayName",
    defaultMessage: "Name",
    description: "Field",
  },
  legalName: { id: "contacts.form.legalName", defaultMessage: "Legal name", description: "Field" },
  roles: { id: "contacts.form.roles", defaultMessage: "Roles", description: "Fieldset" },
  bn: { id: "contacts.form.bn", defaultMessage: "Business Number (BN)", description: "Field" },
  taxId: { id: "contacts.form.taxId", defaultMessage: "Other tax ID", description: "Field" },
  currency: { id: "contacts.form.currency", defaultMessage: "Currency", description: "Field" },
  firstName: { id: "contacts.form.firstName", defaultMessage: "First name", description: "Field" },
  lastName: { id: "contacts.form.lastName", defaultMessage: "Last name", description: "Field" },
  email: { id: "contacts.form.email", defaultMessage: "Email", description: "Field" },
  phone: { id: "contacts.form.phone", defaultMessage: "Telephone", description: "Field" },
  primary: { id: "contacts.form.primary", defaultMessage: "Primary person", description: "Radio" },
  personLegend: {
    id: "contacts.form.personLegend",
    defaultMessage: "Person {n}",
    description: "Fieldset of one person",
  },
  addPerson: {
    id: "contacts.form.addPerson",
    defaultMessage: "Add a person",
    description: "Button",
  },
  removePerson: {
    id: "contacts.form.removePerson",
    defaultMessage: "Remove person {n}",
    description: "Button",
  },
  billing: {
    id: "contacts.form.billing",
    defaultMessage: "Billing address",
    description: "Fieldset",
  },
  shipping: {
    id: "contacts.form.shipping",
    defaultMessage: "Shipping address",
    description: "Fieldset",
  },
  line1: {
    id: "contacts.form.line1",
    defaultMessage: "Street address or PO box",
    description: "Field",
  },
  line2: { id: "contacts.form.line2", defaultMessage: "Address line 2", description: "Field" },
  city: { id: "contacts.form.city", defaultMessage: "City", description: "Field" },
  province: { id: "contacts.form.province", defaultMessage: "Province", description: "Field" },
  provinces: { id: "contacts.form.provinces", defaultMessage: "Provinces", description: "Group" },
  territories: {
    id: "contacts.form.territories",
    defaultMessage: "Territories",
    description: "Group",
  },
  postalCode: {
    id: "contacts.form.postalCode",
    defaultMessage: "Postal code",
    description: "Field",
  },
  creditLimit: {
    id: "contacts.form.creditLimit",
    defaultMessage: "Credit limit",
    description: "Field",
  },
  creditMode: {
    id: "contacts.form.creditMode",
    defaultMessage: "Over the limit",
    description: "Radio group",
  },
  creditWarn: {
    id: "contacts.form.creditWarn",
    defaultMessage: "Warn",
    description: "Option",
  },
  creditBlock: {
    id: "contacts.form.creditBlock",
    defaultMessage: "Block until approved",
    description: "Option",
  },
  salesAccount: {
    id: "contacts.form.salesAccount",
    defaultMessage: "Default sales account",
    description: "Field",
  },
  purchaseAccount: {
    id: "contacts.form.purchaseAccount",
    defaultMessage: "Default purchase account",
    description: "Field",
  },
  noAccount: {
    id: "contacts.form.noAccount",
    defaultMessage: "No account matches",
    description: "Picker",
  },
  typeAsset: { id: "contacts.form.typeAsset", defaultMessage: "Assets", description: "Group" },
  typeLiability: {
    id: "contacts.form.typeLiability",
    defaultMessage: "Liabilities",
    description: "Group",
  },
  typeEquity: { id: "contacts.form.typeEquity", defaultMessage: "Equity", description: "Group" },
  typeRevenue: { id: "contacts.form.typeRevenue", defaultMessage: "Revenue", description: "Group" },
  typeExpense: {
    id: "contacts.form.typeExpense",
    defaultMessage: "Expenses",
    description: "Group",
  },
  save: { id: "contacts.form.save", defaultMessage: "Save contact", description: "Button" },
  saved: { id: "contacts.form.saved", defaultMessage: "Contact saved", description: "Status" },
  fixErrors: {
    id: "contacts.form.fixErrors",
    defaultMessage: "Check the highlighted fields: {message}",
    description: "Error summary",
  },
  loadFailed: {
    id: "contacts.form.loadFailed",
    defaultMessage: "We couldn't load this contact",
    description: "Error",
  },
  retry: { id: "contacts.form.retry", defaultMessage: "Try again", description: "Retry" },
  back: { id: "contacts.form.back", defaultMessage: "All contacts", description: "Link" },
  mergedInto: {
    id: "contacts.form.mergedInto",
    defaultMessage: "This contact was merged into {name}.",
    description: "Notice on a merged contact",
  },
  // merge dialog (B-01-T17)
  mergeTitle: {
    id: "contacts.merge.title",
    defaultMessage: "Merge {merged} into {survivor}",
    description: "Dialog title",
  },
  mergeIntro: {
    id: "contacts.merge.intro",
    defaultMessage:
      "Choose which value to keep for each field. {merged} stays as an alias, so its history and number still lead here.",
    description: "Dialog",
  },
  mergeField: { id: "contacts.merge.field", defaultMessage: "Field", description: "Column" },
  keepFrom: {
    id: "contacts.merge.keepFrom",
    defaultMessage: "Keep for {field}",
    description: "Radio group name",
  },
  mergeMoves: {
    id: "contacts.merge.moves",
    defaultMessage:
      "{count, plural, one {# record} other {# records}} of {records} move to {survivor}",
    description: "Preview line",
  },
  mergeKeeps: {
    id: "contacts.merge.keeps",
    defaultMessage:
      "{count, plural, one {# record} other {# records}} of {records} stay on the alias (posted, can't change)",
    description: "Preview line",
  },
  mergeNothing: {
    id: "contacts.merge.nothing",
    defaultMessage: "No records to move.",
    description: "Preview",
  },
  mergeConfirm: {
    id: "contacts.merge.confirm",
    defaultMessage: "Merge contacts",
    description: "Button",
  },
  mergeCancel: { id: "contacts.merge.cancel", defaultMessage: "Cancel", description: "Button" },
  mergeClose: { id: "contacts.merge.close", defaultMessage: "Close", description: "× button" },
  mergeDone: {
    id: "contacts.merge.done",
    defaultMessage: "{merged} was merged into {survivor}.",
    description: "After merging",
  },
});
