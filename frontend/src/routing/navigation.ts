/**
 * Primary navigation of the organisation app (A-10-T05). Task-first modules that exist in Phase 0
 * (Phase 0 plan §3.2): Home · Contacts · Accounting · Documents · Settings. Each item opens a module
 * from the route registry; later deliverables add Sales, Purchases, Banking, Tax, Payroll,
 * Inventory and Reports here when their modules exist.
 */
import { defineMessages, formatMessage, type MessageDescriptor } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

const labels = defineMessages({
  home: { id: "shell.nav.home", defaultMessage: "Home", description: "Top navigation item" },
  contacts: {
    id: "shell.nav.contacts",
    defaultMessage: "Contacts",
    description: "Top navigation item",
  },
  accounting: {
    id: "shell.nav.accounting",
    defaultMessage: "Accounting",
    description: "Top navigation item: chart of accounts, journals",
  },
  documents: {
    id: "shell.nav.documents",
    defaultMessage: "Documents",
    description: "Top navigation item: documents inbox",
  },
  settings: {
    id: "shell.nav.settings",
    defaultMessage: "Settings",
    description: "Top navigation item: organisation settings",
  },
});

export interface PrimaryNavEntry {
  id: string;
  label: MessageDescriptor;
  /** Module opened by the item (a path of the route registry). */
  modulePath: string;
  /** Module paths that belong to this item: the item itself and everything below `section/`. */
  section: string;
}

export const PRIMARY_NAV: readonly PrimaryNavEntry[] = [
  { id: "home", label: labels.home, modulePath: "home", section: "home" },
  { id: "contacts", label: labels.contacts, modulePath: "contacts", section: "contacts" },
  {
    id: "accounting",
    label: labels.accounting,
    modulePath: "accounting/chart-of-accounts",
    section: "accounting",
  },
  { id: "documents", label: labels.documents, modulePath: "documents", section: "documents" },
  { id: "settings", label: labels.settings, modulePath: "settings/general", section: "settings" },
];

/** Navigation entry that owns a module path (`accounting/journals` → Accounting). */
export function navEntryFor(modulePath: string): PrimaryNavEntry | undefined {
  return PRIMARY_NAV.find(
    (entry) => modulePath === entry.section || modulePath.startsWith(`${entry.section}/`),
  );
}

export interface NavLink {
  id: string;
  label: string;
  href: string;
  current: boolean;
}

/** Primary navigation links for an organisation, with the item owning `currentPath` marked. */
export function primaryNav(org: string, currentPath?: string): NavLink[] {
  const current = currentPath === undefined ? undefined : navEntryFor(currentPath);
  return PRIMARY_NAV.map((entry) => ({
    id: entry.id,
    label: formatMessage(entry.label),
    href: orgModuleUrl(org, entry.modulePath),
    current: entry === current,
  }));
}
