import type { PickerTaxCode } from "./TaxCodePicker";
import type { AccountType, PickerAccount } from "./AccountPicker";
import type { PickerContact } from "./ContactPicker";
import type { DatePickerLabels } from "./DatePicker";
import type { DueDateFieldLabels } from "./DueDateField";
import type { PaymentTermOption } from "./dueDates";

/** Sample picker data (Canadian chart of accounts, contacts) for stories and tests. */
export const dateLabels: DatePickerLabels = {
  openCalendar: "Choose date",
  previousMonth: "Previous month",
  nextMonth: "Next month",
  unreadable: "Enter a date like 26 Oct 2026, 26/10/2026 or +30.",
  shortcuts: {
    today: "Today",
    plus7: "In 7 days",
    plus14: "In 14 days",
    plus30: "In 30 days",
    endOfMonth: "End of this month",
    endOfNextMonth: "End of next month",
  },
};

export const typeLabels: Record<AccountType, string> = {
  asset: "Assets",
  liability: "Liabilities",
  equity: "Equity",
  revenue: "Revenue",
  expense: "Expenses",
};

export const sampleAccounts: PickerAccount[] = [
  { id: "a1000", code: "1000", name: "Chequing", type: "asset", detail: "Bank" },
  { id: "a1200", code: "1200", name: "Accounts receivable", type: "asset" },
  { id: "a2100", code: "2100", name: "GST/HST payable", type: "liability" },
  { id: "a2300", code: "2300", name: "Vacation pay payable", type: "liability" },
  { id: "a3000", code: "3000", name: "Owner's equity", type: "equity" },
  { id: "a4000", code: "4000", name: "Sales", type: "revenue" },
  { id: "a4100", code: "4100", name: "Consulting revenue", type: "revenue" },
  { id: "a5000", code: "5000", name: "Cost of goods sold", type: "expense" },
  { id: "a6100", code: "6100", name: "Office supplies", type: "expense" },
  { id: "a6900", code: "6900", name: "Old telephone", type: "expense", archived: true },
];

export const sampleContacts: PickerContact[] = [
  { id: "c1", name: "Maple Leaf Supply Ltd.", email: "ap@mapleleaf.example", roles: ["customer"] },
  { id: "c2", name: "Northern Lights Bakery Inc.", roles: ["customer", "supplier"] },
  { id: "c3", name: "Hydro Ottawa", email: "billing@hydro.example", roles: ["supplier"] },
  { id: "c4", name: "Bay Street Dental", roles: ["customer"], archived: true },
];

/**
 * A slice of the Canadian template chart (C-01, ca_v1) in server tree order, with sub-types,
 * system roles, bank flags and a parent with sub-accounts — for context filtering (C-01-T10).
 */
export const chartAccounts: PickerAccount[] = [
  {
    id: "c1010",
    code: "1010",
    name: "Chequing account",
    type: "asset",
    subtype: "bank",
    isBank: true,
    detail: "Bank",
  },
  {
    id: "c1100",
    code: "1100",
    name: "Accounts receivable",
    type: "asset",
    subtype: "current_asset",
    systemRole: "ar",
  },
  {
    id: "c1200",
    code: "1200",
    name: "Inventory",
    type: "asset",
    subtype: "inventory",
    systemRole: "inventory",
  },
  {
    id: "c1400",
    code: "1400",
    name: "GST/HST receivable (ITCs)",
    type: "asset",
    subtype: "current_asset",
    systemRole: "itc_receivable",
  },
  { id: "c1630", code: "1630", name: "Computer equipment", type: "asset", subtype: "fixed_asset" },
  {
    id: "c2000",
    code: "2000",
    name: "Accounts payable",
    type: "liability",
    subtype: "current_liability",
    systemRole: "ap",
  },
  {
    id: "c2100",
    code: "2100",
    name: "GST/HST payable",
    type: "liability",
    subtype: "sales_tax_control",
    systemRole: "gst_hst_payable",
  },
  {
    id: "c2300",
    code: "2300",
    name: "Customer deposits",
    type: "liability",
    subtype: "current_liability",
  },
  {
    id: "c2400",
    code: "2400",
    name: "Credit card payable",
    type: "liability",
    subtype: "current_liability",
    isBank: true,
  },
  {
    id: "c3200",
    code: "3200",
    name: "Retained earnings",
    type: "equity",
    subtype: "retained_earnings",
    systemRole: "retained_earnings",
  },
  {
    id: "c3210",
    code: "3210",
    name: "Current year earnings",
    type: "equity",
    subtype: "current_year_earnings",
    systemRole: "current_year_earnings",
  },
  {
    id: "c4000",
    code: "4000",
    name: "Sales",
    type: "revenue",
    subtype: "revenue",
    depth: 1,
    postable: false,
  },
  {
    id: "c4001",
    code: "4001",
    name: "Sales — retail",
    type: "revenue",
    subtype: "revenue",
    depth: 2,
  },
  {
    id: "c4002",
    code: "4002",
    name: "Sales — wholesale",
    type: "revenue",
    subtype: "revenue",
    depth: 2,
  },
  { id: "c4500", code: "4500", name: "Interest income", type: "revenue", subtype: "other_income" },
  {
    id: "c6080",
    code: "6080",
    name: "Office supplies",
    type: "expense",
    subtype: "operating_expense",
  },
  {
    id: "c6210",
    code: "6210",
    name: "Vehicle expenses",
    type: "expense",
    subtype: "operating_expense",
    depth: 1,
    postable: false,
  },
  {
    id: "c6211",
    code: "6211",
    name: "Fuel",
    type: "expense",
    subtype: "operating_expense",
    depth: 2,
  },
  {
    id: "c6300",
    code: "6300",
    name: "Salaries and wages",
    type: "expense",
    subtype: "operating_expense",
  },
  {
    id: "c6900",
    code: "6900",
    name: "Old telephone",
    type: "expense",
    subtype: "operating_expense",
    archived: true,
  },
];

/** Tax code versions for the tax code picker (G-01-T14). */
export const sampleTaxCodes: PickerTaxCode[] = [
  {
    id: "s-on",
    code: "sales.ON.standard",
    name: "HST 13 % (Ontario) on sales",
    side: "sales",
    type: "taxable",
    effective_from: "2010-07-01",
    effective_to: null,
    rate: "13",
    detail: "HST (ON) 13 %",
  },
  {
    id: "s-qc",
    code: "sales.QC.standard",
    name: "GST 5 % + QST 9.975 % (Quebec) on sales",
    side: "sales",
    type: "taxable",
    effective_from: "2013-01-01",
    effective_to: null,
    rate: "14.975",
    detail: "GST 5 % · QST 9.975 %",
  },
  {
    id: "s-mb8",
    code: "sales.MB.standard",
    name: "GST 5 % + RST 8 % (Manitoba) on sales",
    side: "sales",
    type: "taxable",
    effective_from: "2013-07-01",
    effective_to: "2019-06-30",
    rate: "13",
  },
  {
    id: "s-zero",
    code: "sales.zero_rated",
    name: "Zero-rated on sales (0 %)",
    side: "sales",
    type: "zero_rated",
    effective_from: "1991-01-01",
    effective_to: null,
    rate: "0",
  },
  {
    id: "s-exempt",
    code: "sales.exempt",
    name: "Exempt on sales",
    side: "sales",
    type: "exempt",
    effective_from: "1991-01-01",
    effective_to: null,
  },
  {
    id: "p-on",
    code: "purchase.ON.standard",
    name: "HST 13 % (Ontario) on purchases",
    side: "purchase",
    type: "taxable",
    effective_from: "2010-07-01",
    effective_to: null,
    rate: "13",
  },
];

export const taxTypeLabels = {
  taxable: "Taxable",
  zero_rated: "Zero-rated",
  exempt: "Exempt",
  out_of_scope: "Out of scope",
} as const;

/** The default terms master (B-01-T05) for the due date field (D-01-T17). */
export const sampleTerms: PaymentTermOption[] = [
  { id: "t0", name: "Due on receipt", terms_type: "days_after_document", days: 0 },
  { id: "t15", name: "Net 15", terms_type: "days_after_document", days: 15 },
  { id: "t30", name: "Net 30", terms_type: "days_after_document", days: 30 },
  { id: "t60", name: "Net 60", terms_type: "days_after_document", days: 60 },
  { id: "teom", name: "EOM", terms_type: "days_after_month_end", days: 0 },
  { id: "t20", name: "20th of next month", terms_type: "day_of_following_month", days: 20 },
];

export const dueDateLabels: DueDateFieldLabels = {
  label: "Due date",
  terms: "Payment terms",
  dueIn: (days) => (days === 0 ? "Due on the invoice date" : `Due in ${days} days`),
  required: "Enter a due date.",
  beforeDate: "The due date is before the invoice date.",
  date: dateLabels,
};
