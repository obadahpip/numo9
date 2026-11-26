import { defineMessages } from "@/i18n";

/** Expense claim form — the claimant's side (E-04-T09, mileage calculator E-04-T10). */
export const fm = defineMessages({
  newHeading: {
    id: "purchases.expenseForm.newHeading",
    defaultMessage: "New expense claim",
    description: "Heading of the claim form for a new claim",
  },
  editHeading: {
    id: "purchases.expenseForm.editHeading",
    defaultMessage: "Edit expense claim",
    description: "Heading of the claim form for a draft or rejected claim",
  },
  titleLabel: {
    id: "purchases.expenseForm.titleLabel",
    defaultMessage: "What is this claim for?",
    description: "Label of the claim title",
  },
  titlePlaceholder: {
    id: "purchases.expenseForm.titlePlaceholder",
    defaultMessage: "e.g. Kingston client visit",
    description: "Placeholder of the claim title",
  },
  titleRequired: {
    id: "purchases.expenseForm.titleRequired",
    defaultMessage: "Say what the claim is for.",
    description: "Error: the title is empty",
  },
  linesLabel: {
    id: "purchases.expenseForm.linesLabel",
    defaultMessage: "Receipts and trips",
    description: "Accessible name of the list of claim lines",
  },
  receiptLegend: {
    id: "purchases.expenseForm.receiptLegend",
    defaultMessage: "Receipt {n}",
    description: "Heading of one receipt card",
  },
  tripLegend: {
    id: "purchases.expenseForm.tripLegend",
    defaultMessage: "Trip {n}",
    description: "Heading of one mileage card",
  },
  date: { id: "purchases.expenseForm.date", defaultMessage: "Date", description: "Field label" },
  merchant: {
    id: "purchases.expenseForm.merchant",
    defaultMessage: "Merchant",
    description: "Field label: where the receipt is from",
  },
  amount: {
    id: "purchases.expenseForm.amount",
    defaultMessage: "Amount paid (tax included)",
    description: "Field label: the receipt total",
  },
  category: {
    id: "purchases.expenseForm.category",
    defaultMessage: "Category",
    description: "Label of the category chips (the expense account)",
  },
  moreCategories: {
    id: "purchases.expenseForm.moreCategories",
    defaultMessage: "More categories",
    description: "List of the categories that have no chip",
  },
  taxCode: {
    id: "purchases.expenseForm.taxCode",
    defaultMessage: "Tax on the receipt",
    description: "Field label: the tax code",
  },
  noTax: {
    id: "purchases.expenseForm.noTax",
    defaultMessage: "No tax (or foreign receipt)",
    description: "Tax code option: none",
  },
  photo: {
    id: "purchases.expenseForm.photo",
    defaultMessage: "Take a photo or choose a file",
    description: "Receipt upload: opens the camera on a phone",
  },
  uploading: {
    id: "purchases.expenseForm.uploading",
    defaultMessage: "Uploading the receipt…",
    description: "Receipt upload in progress",
  },
  uploadFailed: {
    id: "purchases.expenseForm.uploadFailed",
    defaultMessage: "The receipt didn't upload. Try again.",
    description: "Receipt upload failed",
  },
  uploadRefused: {
    id: "purchases.expenseForm.uploadRefused",
    defaultMessage: "Use a photo or a PDF of up to 25 MB.",
    description: "Receipt refused before upload (type or size)",
  },
  attached: {
    id: "purchases.expenseForm.attached",
    defaultMessage: "Attached: {name}",
    description: "The uploaded receipt",
  },
  duplicate: {
    id: "purchases.expenseForm.duplicate",
    defaultMessage:
      "Attached: {name}. This file was uploaded before — make sure it isn't claimed twice.",
    description: "The uploaded receipt is a duplicate of an earlier upload",
  },
  from: { id: "purchases.expenseForm.from", defaultMessage: "From", description: "Trip start" },
  to: { id: "purchases.expenseForm.to", defaultMessage: "To", description: "Trip destination" },
  km: {
    id: "purchases.expenseForm.km",
    defaultMessage: "Distance (km)",
    description: "Field label: kilometres driven",
  },
  mileageAmount: {
    id: "purchases.expenseForm.mileageAmount",
    defaultMessage: "At the CRA rate:",
    description: "Before the live amount of a trip",
  },
  mileageTier: {
    id: "purchases.expenseForm.mileageTier",
    defaultMessage: "{km} km × {rate} = {amount}",
    description: "One rate tier of a trip (first 5,000 km, then the lower rate)",
  },
  rateMissing: {
    id: "purchases.expenseForm.rateMissing",
    defaultMessage: "No mileage rate is set for this date: the amount is worked out when it is.",
    description: "No CRA rate covers the trip's date",
  },
  remove: {
    id: "purchases.expenseForm.remove",
    defaultMessage: "Remove",
    description: "Button: remove this line",
  },
  addReceipt: {
    id: "purchases.expenseForm.addReceipt",
    defaultMessage: "Add a receipt",
    description: "Button",
  },
  addTrip: {
    id: "purchases.expenseForm.addTrip",
    defaultMessage: "Add a trip",
    description: "Button",
  },
  notes: {
    id: "purchases.expenseForm.notes",
    defaultMessage: "Notes for the approver",
    description: "Field label",
  },
  receiptsTotal: {
    id: "purchases.expenseForm.receiptsTotal",
    defaultMessage: "Receipts: {amount}",
    description: "Running total of the receipt amounts",
  },
  saveDraft: {
    id: "purchases.expenseForm.saveDraft",
    defaultMessage: "Save draft",
    description: "Button",
  },
  submit: {
    id: "purchases.expenseForm.submit",
    defaultMessage: "Submit for approval",
    description: "Button",
  },
  saved: {
    id: "purchases.expenseForm.saved",
    defaultMessage: "Draft saved.",
    description: "Status message",
  },
  submitted: {
    id: "purchases.expenseForm.submitted",
    defaultMessage: "Claim {number} submitted for approval.",
    description: "Status message",
  },
  checkLines: {
    id: "purchases.expenseForm.checkLines",
    defaultMessage: "Review the lines: a date, an amount or kilometres are missing.",
    description: "Error: the API refused the lines",
  },
  failed: {
    id: "purchases.expenseForm.failed",
    defaultMessage: "That didn't work and nothing was changed. Try again in a moment.",
    description: "Generic error",
  },
  loading: {
    id: "purchases.expenseForm.loading",
    defaultMessage: "Loading the claim…",
    description: "Placeholder while the claim loads",
  },
});
