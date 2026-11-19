import { defineMessages } from "@/i18n";

/** Contacts import wizard (B-03-T12) and its template / help text (B-03-T13). */
export const m = defineMessages({
  title: { id: "imports.title", defaultMessage: "Import contacts", description: "Heading" },
  steps: { id: "imports.steps", defaultMessage: "Import steps", description: "Step list name" },
  step: {
    id: "imports.step",
    defaultMessage: "Step {n} of 4: {name}",
    description: "Current step",
  },
  stepItem: { id: "imports.stepItem", defaultMessage: "{n}. {name}", description: "Step list" },
  stepUpload: { id: "imports.stepUpload", defaultMessage: "Upload", description: "Step" },
  stepMap: { id: "imports.stepMap", defaultMessage: "Match columns", description: "Step" },
  stepReview: { id: "imports.stepReview", defaultMessage: "Review", description: "Step" },
  stepImport: { id: "imports.stepImport", defaultMessage: "Import", description: "Step" },
  what: { id: "imports.what", defaultMessage: "What are you importing?", description: "Fieldset" },
  entityContacts: {
    id: "imports.entityContacts",
    defaultMessage: "Contacts (one row per contact)",
    description: "Option",
  },
  entityPeople: {
    id: "imports.entityPeople",
    defaultMessage: "People at contacts (one row per person, as many as you like)",
    description: "Option",
  },
  file: {
    id: "imports.file",
    defaultMessage: "CSV or Excel file (25 MB at most)",
    description: "Field",
  },
  upload: { id: "imports.upload", defaultMessage: "Upload file", description: "Button" },
  template: {
    id: "imports.template",
    defaultMessage: "Download a template with the right columns",
    description: "Link",
  },
  help1: {
    id: "imports.help1",
    defaultMessage:
      "Each contact is matched by its External ID, then its contact number — never by its name, so renaming a contact in your file updates it instead of making a copy.",
    description: "Help text",
  },
  help2: {
    id: "imports.help2",
    defaultMessage:
      "An empty cell leaves the value as it is. To empty a field on purpose, type __CLEAR__ in the cell.",
    description: "Help text",
  },
  help3: {
    id: "imports.help3",
    defaultMessage:
      "Nothing is saved until the last step: first you see, row by row, what would be created, changed or refused.",
    description: "Help text",
  },
  uploadFailed: {
    id: "imports.uploadFailed",
    defaultMessage: "We couldn't read the file: {reason}",
    description: "Error",
  },
  columnFor: {
    id: "imports.columnFor",
    defaultMessage: "Field for the column {header}",
    description: "Select name",
  },
  notImported: { id: "imports.notImported", defaultMessage: "Don't import", description: "Option" },
  sampleValues: {
    id: "imports.sampleValues",
    defaultMessage: "e.g. {values}",
    description: "Sample values of a column",
  },
  matchBn: {
    id: "imports.matchBn",
    defaultMessage: "Also match contacts by Business Number when the ID and number are empty",
    description: "Option",
  },
  saveAs: {
    id: "imports.saveAs",
    defaultMessage: "Save this mapping as (optional)",
    description: "Field",
  },
  check: { id: "imports.check", defaultMessage: "Review the file", description: "Button" },
  totals: {
    id: "imports.totals",
    defaultMessage:
      "{create, plural, =0 {No new contacts} one {# new} other {# new}}, {update} to update, {unchanged} unchanged, {error, plural, =0 {no errors} one {# with errors} other {# with errors}}.",
    description: "Dry-run totals",
  },
  filter: { id: "imports.filter", defaultMessage: "Show", description: "Filter" },
  filterAll: { id: "imports.filterAll", defaultMessage: "All rows", description: "Filter" },
  actionCreate: { id: "imports.actionCreate", defaultMessage: "New", description: "Row action" },
  actionUpdate: { id: "imports.actionUpdate", defaultMessage: "Update", description: "Row action" },
  actionUnchanged: {
    id: "imports.actionUnchanged",
    defaultMessage: "Unchanged",
    description: "Row action",
  },
  actionError: { id: "imports.actionError", defaultMessage: "Error", description: "Row action" },
  rowLine: {
    id: "imports.rowLine",
    defaultMessage: "{action} — row {row} · {label}",
    description: "A row of the review",
  },
  change: {
    id: "imports.change",
    defaultMessage: "{field}: {before} → {after}",
    description: "A change",
  },
  errorsCsv: {
    id: "imports.errorsCsv",
    defaultMessage: "Download the errors (CSV)",
    description: "Link",
  },
  back: { id: "imports.back", defaultMessage: "Back", description: "Button" },
  importNow: {
    id: "imports.importNow",
    defaultMessage: "Import {count, plural, one {# row} other {# rows}}",
    description: "Button",
  },
  importing: {
    id: "imports.importing",
    defaultMessage:
      "Importing in the background — follow it in the job tray. You can leave this page.",
    description: "Status",
  },
  done: {
    id: "imports.done",
    defaultMessage: "Import finished.",
    description: "Status",
  },
  failed: {
    id: "imports.failed",
    defaultMessage: "We couldn't do that: {reason}",
    description: "Error",
  },
});
