import { defineMessages } from "@/i18n";

/** Conversion balances wizard (C-05-T10). */
export const cm = defineMessages({
  title: {
    id: "conversion.wizard.title",
    defaultMessage: "Conversion balances",
    description: "Page heading",
  },
  intro: {
    id: "conversion.wizard.intro",
    defaultMessage:
      "Start with the right numbers: the balances of your old books at the conversion date, and the invoices and bills still open. Each step is saved as you go — you can leave and come back.",
    description: "Text under the heading",
  },
  steps: {
    id: "conversion.wizard.steps",
    defaultMessage: "Conversion steps",
    description: "Accessible name of the stepper",
  },
  stepDate: {
    id: "conversion.wizard.stepDate",
    defaultMessage: "Conversion date",
    description: "Wizard step",
  },
  stepBank: {
    id: "conversion.wizard.stepBank",
    defaultMessage: "Bank and cash",
    description: "Wizard step",
  },
  stepInvoices: {
    id: "conversion.wizard.stepInvoices",
    defaultMessage: "Open invoices",
    description: "Wizard step",
  },
  stepBills: {
    id: "conversion.wizard.stepBills",
    defaultMessage: "Open bills",
    description: "Wizard step",
  },
  stepOther: {
    id: "conversion.wizard.stepOther",
    defaultMessage: "Other balances",
    description: "Wizard step",
  },
  stepReview: {
    id: "conversion.wizard.stepReview",
    defaultMessage: "Review and finalise",
    description: "Wizard step",
  },
  stepState: {
    id: "conversion.wizard.stepState",
    defaultMessage: "{n}. {name}{done, select, yes { (done)} other {}}",
    description: "Accessible name of a step in the stepper",
  },
  next: {
    id: "conversion.wizard.next",
    defaultMessage: "Save and continue",
    description: "Button",
  },
  back: { id: "conversion.wizard.back", defaultMessage: "Back", description: "Button" },
  save: { id: "conversion.wizard.save", defaultMessage: "Save", description: "Button" },
  saved: { id: "conversion.wizard.saved", defaultMessage: "Saved.", description: "Status" },
  loading: { id: "conversion.wizard.loading", defaultMessage: "Loading…", description: "Status" },
  failed: {
    id: "conversion.wizard.failed",
    defaultMessage: "That didn't work and nothing was changed. Try again in a moment.",
    description: "Error",
  },
  dateLabel: {
    id: "conversion.wizard.dateLabel",
    defaultMessage: "Conversion date",
    description: "Field label",
  },
  dateHelp: {
    id: "conversion.wizard.dateHelp",
    defaultMessage:
      "The first day your books are kept in Numo9 — usually the day after the last closed period in your old system. Balances are entered as at the day before.",
    description: "Field help",
  },
  start: {
    id: "conversion.wizard.start",
    defaultMessage: "Start the conversion",
    description: "Button",
  },
  bankIntro: {
    id: "conversion.wizard.bankIntro",
    defaultMessage:
      "Enter each bank and cash account's balance from its statement at the day before the conversion date. An overdrawn account is a credit.",
    description: "Bank step text",
  },
  otherIntro: {
    id: "conversion.wizard.otherIntro",
    defaultMessage:
      "Enter every other balance of your old trial balance: Accounts receivable and payable (they must equal the open documents), loans, share capital, retained earnings… Nothing is plugged: if you need a suspense amount, add a line on Conversion balances suspense yourself — it stays visible and is flagged for review.",
    description: "Other balances step text",
  },
  account: { id: "conversion.wizard.account", defaultMessage: "Account", description: "Column" },
  debit: { id: "conversion.wizard.debit", defaultMessage: "Debit", description: "Column" },
  credit: { id: "conversion.wizard.credit", defaultMessage: "Credit", description: "Column" },
  description: {
    id: "conversion.wizard.description",
    defaultMessage: "Description",
    description: "Column",
  },
  accountOfLine: {
    id: "conversion.wizard.accountOfLine",
    defaultMessage: "Account, line {line}",
    description: "Accessible name",
  },
  debitOfLine: {
    id: "conversion.wizard.debitOfLine",
    defaultMessage: "Debit, line {line}",
    description: "Accessible name",
  },
  creditOfLine: {
    id: "conversion.wizard.creditOfLine",
    defaultMessage: "Credit, line {line}",
    description: "Accessible name",
  },
  descriptionOfLine: {
    id: "conversion.wizard.descriptionOfLine",
    defaultMessage: "Description, line {line}",
    description: "Accessible name",
  },
  removeLine: {
    id: "conversion.wizard.removeLine",
    defaultMessage: "Remove line {line}",
    description: "Button (accessible name)",
  },
  addLine: { id: "conversion.wizard.addLine", defaultMessage: "Add a line", description: "Button" },
  chooseAccount: {
    id: "conversion.wizard.chooseAccount",
    defaultMessage: "Choose an account",
    description: "Placeholder",
  },
  rowProblem: {
    id: "conversion.wizard.rowProblem",
    defaultMessage: "Line {line}: {message}",
    description: "A problem of one line, listed after saving",
  },
  reviewIntro: {
    id: "conversion.wizard.reviewIntro",
    defaultMessage:
      "Review the totals and the receivable and payable controls, then finalise: one opening journal is posted, dated the conversion date. After that, balances are corrected by your adviser with a correcting journal.",
    description: "Review step text",
  },
  control: {
    id: "conversion.wizard.control",
    defaultMessage: "{label}: {control} · open documents {documents} ({count})",
    description: "A control line against its documents",
  },
  equityMissing: {
    id: "conversion.wizard.equityMissing",
    defaultMessage:
      "No equity balance was entered (share capital, retained earnings…). That's unusual for an existing business — check the old balance sheet.",
    description: "Review warning",
  },
  lockBalances: {
    id: "conversion.wizard.lockBalances",
    defaultMessage:
      "Lock balances: stop everyone except advisers from changing anything dated before the conversion date",
    description: "Checkbox",
  },
  finalised: {
    id: "conversion.wizard.finalised",
    defaultMessage: "Finalised on {date}: opening journal {number}.",
    description: "Status of a finalised conversion",
  },
  corrections: {
    id: "conversion.wizard.corrections",
    defaultMessage:
      "{count, plural, =0 {No corrections} one {# correcting journal} other {# correcting journals}}",
    description: "Count of correcting journals",
  },
});
