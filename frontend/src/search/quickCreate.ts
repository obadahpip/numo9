/**
 * Quick-create registry (A-09-T06): every "create" action of the app with its keyboard shortcut —
 * press `N` then the letter (`N C` → new contact) anywhere in an organisation, or pick it in the
 * command palette (Ctrl/⌘+K). Each entry names the permission and the package feature it needs:
 * the palette hides what the user may not do and shows what the package lacks locked, with the
 * reason. Entries whose screen arrives in a later phase are listed (the shortcut sheet documents
 * every shortcut) but marked `availableIn` and not offered yet.
 */
import { defineMessages, type MessageDescriptor } from "@/i18n";

const m = defineMessages({
  invoice: {
    id: "quickCreate.invoice",
    defaultMessage: "New invoice",
    description: "Quick-create",
  },
  bill: { id: "quickCreate.bill", defaultMessage: "New bill", description: "Quick-create" },
  contact: {
    id: "quickCreate.contact",
    defaultMessage: "New contact",
    description: "Quick-create",
  },
  quote: { id: "quickCreate.quote", defaultMessage: "New quote", description: "Quick-create" },
  purchaseOrder: {
    id: "quickCreate.purchaseOrder",
    defaultMessage: "New purchase order",
    description: "Quick-create",
  },
  journal: {
    id: "quickCreate.journal",
    defaultMessage: "New manual journal",
    description: "Quick-create",
  },
  spend: {
    id: "quickCreate.spend",
    defaultMessage: "Spend money",
    description: "Quick-create: a bank payment",
  },
  receive: {
    id: "quickCreate.receive",
    defaultMessage: "Receive money",
    description: "Quick-create: a bank receipt",
  },
  transfer: {
    id: "quickCreate.transfer",
    defaultMessage: "Transfer money",
    description: "Quick-create: between bank accounts",
  },
  user: { id: "quickCreate.user", defaultMessage: "Invite a user", description: "Quick-create" },
});

export interface QuickCreate {
  id: string;
  /** The key pressed after `N`. */
  key: string;
  label: MessageDescriptor;
  /** Under `/o/<org>/`. */
  path: string;
  permission: string;
  feature: string;
  /** The phase whose screen this opens; absent = available now. */
  availableIn?: string;
}

export const QUICK_CREATE: readonly QuickCreate[] = [
  {
    id: "invoice",
    key: "I",
    label: m.invoice,
    path: "sales/invoices/new",
    permission: "sales.invoices.manage",
    feature: "accounting.sales_invoices.write",
    availableIn: "Phase 1",
  },
  {
    id: "bill",
    key: "B",
    label: m.bill,
    path: "purchases/bills/new",
    permission: "purchases.bills.manage",
    feature: "accounting.bills.write",
    availableIn: "Phase 1",
  },
  {
    id: "contact",
    key: "C",
    label: m.contact,
    path: "contacts/new",
    permission: "contacts.contacts.manage",
    feature: "accounting.contacts.write",
  },
  {
    id: "quote",
    key: "Q",
    label: m.quote,
    path: "sales/quotes/new",
    permission: "sales.quotes.manage",
    feature: "accounting.quotes.write",
    availableIn: "Phase 1",
  },
  {
    id: "purchase-order",
    key: "P",
    label: m.purchaseOrder,
    path: "purchases/orders/new",
    permission: "purchases.orders.manage",
    feature: "accounting.purchase_orders.write",
    availableIn: "Phase 1",
  },
  {
    id: "journal",
    key: "J",
    label: m.journal,
    path: "accounting/journals/new",
    permission: "accounting.journals.post",
    feature: "accounting.journals.write",
  },
  {
    id: "spend",
    key: "S",
    label: m.spend,
    path: "banking/spend",
    permission: "banking.transactions.manage",
    feature: "accounting.banking.write",
    availableIn: "Phase 1",
  },
  {
    id: "receive",
    key: "R",
    label: m.receive,
    path: "banking/receive",
    permission: "banking.transactions.manage",
    feature: "accounting.banking.write",
    availableIn: "Phase 1",
  },
  {
    id: "transfer",
    key: "T",
    label: m.transfer,
    path: "banking/transfer",
    permission: "banking.transactions.manage",
    feature: "accounting.banking.write",
    availableIn: "Phase 1",
  },
  {
    id: "user",
    key: "U",
    label: m.user,
    path: "settings/users-roles?invite=1",
    permission: "organisation.members.invite",
    feature: "core",
  },
];

/** The shortcut of an entry as written in the UI: "N C". */
export function shortcutOf(entry: QuickCreate): string {
  return `N ${entry.key}`;
}

/** The entry for the key pressed after `N` (case-insensitive), if any. */
export function quickCreateFor(key: string): QuickCreate | undefined {
  const upper = key.toUpperCase();
  return QUICK_CREATE.find((entry) => entry.key === upper);
}

export function quickCreateUrl(org: string, entry: QuickCreate): string {
  return `/o/${org}/${entry.path}`;
}

/** What the palette offers: available now, permitted; `locked` when the package lacks it. */
export function offeredQuickCreates(
  permissions: ReadonlySet<string> | null,
  locked: (feature: string) => string | null,
): { entry: QuickCreate; reason: string | null }[] {
  return QUICK_CREATE.filter(
    (entry) => !entry.availableIn && (permissions === null || permissions.has(entry.permission)),
  ).map((entry) => ({ entry, reason: entry.feature === "core" ? null : locked(entry.feature) }));
}
