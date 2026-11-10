import type { AccountType, PickerAccount } from "./AccountPicker";
import type { PickerContact } from "./ContactPicker";
import type { DatePickerLabels } from "./DatePicker";

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
