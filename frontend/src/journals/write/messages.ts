import { defineMessages } from "@/i18n";

export const wm = defineMessages({
  title: {
    id: "journals.write.title",
    defaultMessage: "New manual journal",
    description: "Heading of the manual journal screen",
  },
  date: { id: "journals.write.date", defaultMessage: "Date", description: "Field" },
  narration: {
    id: "journals.write.narration",
    defaultMessage: "Narration",
    description: "Field: what the journal is for",
  },
  autoReverse: {
    id: "journals.write.autoReverse",
    defaultMessage: "Reverse automatically on (optional)",
    description: "Field: date the journal's reversal is posted by itself",
  },
  type: {
    id: "journals.write.type",
    defaultMessage: "Journal type",
    description: "Legend of the journal type segmented control",
  },
  typeGeneral: { id: "journals.type.general", defaultMessage: "General", description: "Type" },
  typeAdjusting: {
    id: "journals.type.adjusting",
    defaultMessage: "Adjusting",
    description: "Journal type",
  },
  typeReclass: { id: "journals.type.reclass", defaultMessage: "Reclass", description: "Type" },
  typeTaxAdjustment: {
    id: "journals.type.taxAdjustment",
    defaultMessage: "Tax adjustment",
    description: "Journal type",
  },
  helpGeneral: {
    id: "journals.typeHelp.general",
    defaultMessage: "An everyday entry: anything that isn't one of the other types.",
    description: "Description of the General journal type",
  },
  helpAdjusting: {
    id: "journals.typeHelp.adjusting",
    defaultMessage: "Accruals, prepayments and other period-end adjustments.",
    description: "Description of the Adjusting journal type",
  },
  helpReclass: {
    id: "journals.typeHelp.reclass",
    defaultMessage: "Moves an amount from one account to another; the total doesn't change.",
    description: "Description of the Reclass journal type",
  },
  helpTaxAdjustment: {
    id: "journals.typeHelp.taxAdjustment",
    defaultMessage: "Tax book only (CCA, book-to-tax differences); never a bank account.",
    description: "Description of the Tax adjustment journal type",
  },
  lines: { id: "journals.write.lines", defaultMessage: "Lines", description: "Table caption" },
  account: { id: "journals.write.account", defaultMessage: "Account", description: "Column" },
  debit: { id: "journals.write.debit", defaultMessage: "Debit", description: "Column" },
  credit: { id: "journals.write.credit", defaultMessage: "Credit", description: "Column" },
  description: {
    id: "journals.write.description",
    defaultMessage: "Description",
    description: "Column",
  },
  accountOfLine: {
    id: "journals.write.accountOfLine",
    defaultMessage: "Account, line {line, number}",
    description: "Accessible name of a line's account picker",
  },
  debitOfLine: {
    id: "journals.write.debitOfLine",
    defaultMessage: "Debit, line {line, number}",
    description: "Accessible name of a line's debit field",
  },
  creditOfLine: {
    id: "journals.write.creditOfLine",
    defaultMessage: "Credit, line {line, number}",
    description: "Accessible name of a line's credit field",
  },
  descriptionOfLine: {
    id: "journals.write.descriptionOfLine",
    defaultMessage: "Description, line {line, number}",
    description: "Accessible name of a line's description field",
  },
  chooseAccount: {
    id: "journals.write.chooseAccount",
    defaultMessage: "Choose an account",
    description: "Empty option of a line's account picker",
  },
  addLine: { id: "journals.write.addLine", defaultMessage: "Add a line", description: "Button" },
  totals: {
    id: "journals.write.totals",
    defaultMessage: "Debits {debit} · Credits {credit}",
    description: "Totals under the lines",
  },
  post: { id: "journals.write.post", defaultMessage: "Post journal", description: "Button" },
  saveDraft: {
    id: "journals.write.saveDraft",
    defaultMessage: "Save as draft",
    description: "Button",
  },
  posting: { id: "journals.write.posting", defaultMessage: "Posting…", description: "Busy" },
  problems: {
    id: "journals.write.problems",
    defaultMessage: "Fix these before posting",
    description: "Heading of the list of problems",
  },
  failed: {
    id: "journals.write.failed",
    defaultMessage: "The journal couldn't be saved. Make sure you're online, then try again.",
    description: "Network or server failure",
  },
  accountOption: {
    id: "journals.write.accountOption",
    defaultMessage: "{code} · {name}",
    description: "An account in a line's picker: code and name",
  },
  retry: { id: "journals.write.retry", defaultMessage: "Try again", description: "Button" },
  loading: {
    id: "journals.write.loading",
    defaultMessage: "Loading accounts…",
    description: "While the chart of accounts loads",
  },
  blocked: {
    id: "journals.write.blocked",
    defaultMessage:
      "A journal can't take a bank or cash account below zero. Record the money coming in first, or ask your adviser.",
    description: "Shown to people who aren't advisers when the journal would overdraw cash",
  },
  overrideTitle: {
    id: "journals.write.overrideTitle",
    defaultMessage: "Post below zero?",
    description: "Title of the adviser override dialog",
  },
  overrideBody: {
    id: "journals.write.overrideBody",
    defaultMessage:
      "As an adviser you may post it anyway. The reason is kept with the journal and in the audit log.",
    description: "Explanation in the adviser override dialog",
  },
  overrideReason: {
    id: "journals.write.overrideReason",
    defaultMessage: "Reason (at least {min, number} characters)",
    description: "Label of the override reason field",
  },
  overrideConfirm: {
    id: "journals.write.overrideConfirm",
    defaultMessage: "Post with this reason",
    description: "Button: post past the cash guard",
  },
  cancel: { id: "journals.write.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "journals.write.close", defaultMessage: "Close", description: "Close the dialog" },
  attachments: {
    id: "journals.write.attachments",
    defaultMessage: "Supporting documents",
    description: "Heading of the journal's attachment drop zone",
  },
  attachHint: {
    id: "journals.write.attachHint",
    defaultMessage: "Drop a receipt or invoice here, or choose a file.",
    description: "Text in the attachment drop zone",
  },
  attachButton: {
    id: "journals.write.attachButton",
    defaultMessage: "Attach a document",
    description: "File picker of the journal's drop zone",
  },
  attachmentRequired: {
    id: "journals.write.attachmentRequired",
    defaultMessage: "This journal needs a supporting document before it can be posted.",
    description: "Drop zone message when an attachment is required",
  },
  postNeedsAttachment: {
    id: "journals.write.postNeedsAttachment",
    defaultMessage: "Attach the supporting document first.",
    description: "Why Post is disabled: an attachment is required",
  },
  uploading: {
    id: "journals.write.uploading",
    defaultMessage: "Uploading {name}…",
    description: "While a document uploads",
  },
  uploadFailed: {
    id: "journals.write.uploadFailed",
    defaultMessage: "{name} couldn't be uploaded. Try again.",
    description: "A document upload failed",
  },
});
