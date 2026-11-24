/**
 * Primary navigation of the organisation app (A-10-T05). Task-first modules that exist in Phase 0
 * (Phase 0 plan §3.2): Home · Contacts · Accounting · Documents · Settings. Each item opens a module
 * from the route registry; later deliverables add Sales, Purchases, Banking, Tax, Payroll,
 * Inventory and Reports here when their modules exist.
 *
 * Gated modules (U-03-T11): an item whose module's feature key isn't in the organisation's
 * package stays in the navigation, with a lock glyph and "<Product> isn't in this organisation's
 * package" as its tooltip. The link still opens the module, which shows its locked panel — the
 * item is never hidden and the route never redirects (gap-14).
 */
import type { FeatureDecision } from "@numo9/ui";

import { CORE } from "@/catalogue/features";
import { defineMessages, type FormatMessage, type MessageDescriptor } from "@/i18n";
import {
  findOrgModule,
  orgModuleUrl,
  practiceDirectoryUrl,
  practiceGroupsUrl,
  practiceHomeUrl,
  practiceStaffUrl,
} from "@/routing/routes";

const labels = defineMessages({
  home: { id: "shell.nav.home", defaultMessage: "Home", description: "Top navigation item" },
  practiceHome: {
    id: "shell.practiceNav.home",
    defaultMessage: "Dashboard",
    description: "Practice navigation: the practice home (V-04)",
  },
  practiceDirectory: {
    id: "shell.practiceNav.directory",
    defaultMessage: "Directory",
    description: "Practice navigation: organisation directory",
  },
  practiceGroups: {
    id: "shell.practiceNav.groups",
    defaultMessage: "Groups & tags",
    description: "Practice navigation",
  },
  practiceStaff: {
    id: "shell.practiceNav.staff",
    defaultMessage: "Staff",
    description: "Practice navigation",
  },
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
  banking: {
    id: "shell.nav.banking",
    defaultMessage: "Banking",
    description: "Top navigation item: bank, credit card and cash accounts (F-01)",
  },
  reports: {
    id: "shell.nav.reports",
    defaultMessage: "Reports",
    description: "Top navigation item: the report home (K-01)",
  },
  settings: {
    id: "shell.nav.settings",
    defaultMessage: "Settings",
    description: "Top navigation item: organisation settings",
  },
  locked: {
    id: "shell.nav.locked",
    defaultMessage: "{product} isn't in this organisation's package",
    description: "Tooltip of a navigation item whose module is not in the package (lock glyph)",
  },
  lockedUnknown: {
    id: "shell.nav.lockedUnknown",
    defaultMessage: "Not in this organisation's package",
    description: "Tooltip of a locked navigation item when the product is not known",
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
  { id: "banking", label: labels.banking, modulePath: "banking", section: "banking" },
  { id: "reports", label: labels.reports, modulePath: "reports", section: "reports" },
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
  /** The module isn't in the package: lock glyph + this tooltip (U-03-T11). */
  locked?: { label: string };
}

/** Decision for a feature key (the entitlement store's `decide`). */
export type FeatureLookup = (feature: string) => FeatureDecision;

/**
 * Primary navigation links for an organisation, with the item owning `currentPath` marked and,
 * given the entitlement store's decisions, the items whose module is gated locked.
 */
export function primaryNav(
  fm: FormatMessage,
  org: string,
  currentPath?: string,
  feature?: FeatureLookup,
): NavLink[] {
  const current = currentPath === undefined ? undefined : navEntryFor(currentPath);
  return PRIMARY_NAV.map((entry) => {
    const link: NavLink = {
      id: entry.id,
      label: fm(entry.label),
      href: orgModuleUrl(org, entry.modulePath),
      current: entry === current,
    };
    const key = findOrgModule(entry.modulePath)?.feature ?? CORE;
    const decision = feature && key !== CORE ? feature(key) : undefined;
    if (decision?.state === "gated") {
      const product = decision.productName ?? decision.product;
      link.locked = {
        label: product ? fm(labels.locked, { product }) : fm(labels.lockedUnknown),
      };
    }
    return link;
  });
}

/** Practice navigation (V-04): dashboard, directory, groups & tags, staff; the item owning
 * `currentPath` (`/p/x/staff/…` → Staff) marked. */
export function practiceNav(fm: FormatMessage, practice: string, currentPath = ""): NavLink[] {
  const entries = [
    { id: "practice-home", label: labels.practiceHome, href: practiceHomeUrl(practice) },
    {
      id: "practice-directory",
      label: labels.practiceDirectory,
      href: practiceDirectoryUrl(practice),
    },
    { id: "practice-groups", label: labels.practiceGroups, href: practiceGroupsUrl(practice) },
    { id: "practice-staff", label: labels.practiceStaff, href: practiceStaffUrl(practice) },
  ];
  const path = currentPath.replace(/\/+$/, "");
  return entries.map((entry) => ({
    id: entry.id,
    label: fm(entry.label),
    href: entry.href,
    current:
      entry.id === "practice-home"
        ? path === entry.href
        : path === entry.href || path.startsWith(`${entry.href}/`),
  }));
}
