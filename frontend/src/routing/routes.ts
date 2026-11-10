/**
 * Route registry (S-01-T14): the canonical organisation-app URLs that exist today and the
 * legacy-style aliases that redirect to them. Later deliverables add their modules here so the
 * redirect map, the 404 page search and the `gap-02` crawler stay in step with the real routes.
 *
 * URL scheme (Phase 0 information architecture): `/o/:org/<module>`, e.g. `/o/acme/home`.
 */
import { defineMessages, type MessageDescriptor } from "@/i18n";

/** Organisation slug: lowercase letters, digits and inner hyphens, 1–63 characters. */
export const ORG_SLUG = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

/** Cookie holding the last organisation the user opened (written by the org switcher, A-10/V-01). */
export const CURRENT_ORG_COOKIE = "numo9_org";

const labels = defineMessages({
  home: {
    id: "routes.home",
    defaultMessage: "Home",
    description: "Module name: organisation home",
  },
  contacts: { id: "routes.contacts", defaultMessage: "Contacts", description: "Module name" },
  chartOfAccounts: {
    id: "routes.chartOfAccounts",
    defaultMessage: "Chart of accounts",
    description: "Module name (Accounting)",
  },
  journals: {
    id: "routes.journals",
    defaultMessage: "Journals",
    description: "Module name (Accounting)",
  },
  documents: { id: "routes.documents", defaultMessage: "Documents", description: "Module name" },
  settingsGeneral: {
    id: "routes.settingsGeneral",
    defaultMessage: "Settings: General",
    description: "Settings section: organisation details",
  },
  settingsRegistrations: {
    id: "routes.settingsRegistrations",
    defaultMessage: "Settings: Tax registrations",
    description: "Settings section: BN, GST/HST, QST registrations",
  },
  settingsLockDates: {
    id: "routes.settingsLockDates",
    defaultMessage: "Settings: Lock dates",
    description: "Settings section",
  },
  settingsUsersRoles: {
    id: "routes.settingsUsersRoles",
    defaultMessage: "Settings: Users and roles",
    description: "Settings section",
  },
  settingsEmailDomain: {
    id: "routes.settingsEmailDomain",
    defaultMessage: "Settings: Email domain",
    description: "Settings section",
  },
  settingsSubscription: {
    id: "routes.settingsSubscription",
    defaultMessage: "Settings: Subscription",
    description: "Settings section",
  },
  settingsNumbering: {
    id: "routes.settingsNumbering",
    defaultMessage: "Settings: Numbering",
    description: "Settings section",
  },
  settingsCustomFields: {
    id: "routes.settingsCustomFields",
    defaultMessage: "Settings: Custom fields",
    description: "Settings section",
  },
  settingsAuditLog: {
    id: "routes.settingsAuditLog",
    defaultMessage: "Settings: Audit log",
    description: "Settings section",
  },
});

export interface OrgModule {
  /** Path below `/o/:org/`, lowercase, no leading or trailing slash. */
  path: string;
  label: MessageDescriptor;
  /**
   * Legacy-style paths (lowercase, no leading slash) that land on this module: Numo9 short
   * forms, common words and the Xero URLs Profitex staff have bookmarked (teardown §0–§6).
   */
  aliases: readonly string[];
}

export const ORG_MODULES: readonly OrgModule[] = [
  {
    path: "home",
    label: labels.home,
    aliases: [
      "homepage",
      "dashboard",
      "overview",
      "start",
      "app",
      "index",
      "index.html",
      "default.aspx",
      "home.aspx",
      "dashboard.aspx",
    ],
  },
  {
    path: "contacts",
    label: labels.contacts,
    aliases: [
      "contact",
      "customers",
      "suppliers",
      "contacts/all",
      "contacts/customers",
      "contacts/suppliers",
    ],
  },
  {
    path: "accounting/chart-of-accounts",
    label: labels.chartOfAccounts,
    aliases: [
      "accounting",
      "accounts",
      "chart-of-accounts",
      "chartofaccounts",
      "coa",
      "generalledger/chartofaccounts.aspx",
    ],
  },
  {
    path: "accounting/journals",
    label: labels.journals,
    aliases: ["journals", "journal", "manual-journals", "journal/search.aspx"],
  },
  {
    path: "documents",
    label: labels.documents,
    aliases: ["document", "files", "inbox"],
  },
  {
    path: "settings/general",
    label: labels.settingsGeneral,
    aliases: [
      "settings",
      "setup",
      "preferences",
      "organisation-settings",
      "organization-settings",
      "settings/organisation",
      "settings/organization",
      "setup/financialsettings.aspx",
    ],
  },
  {
    path: "settings/registrations",
    label: labels.settingsRegistrations,
    aliases: ["settings/tax", "tax-settings", "registrations"],
  },
  {
    path: "settings/lock-dates",
    label: labels.settingsLockDates,
    aliases: ["lock-dates", "settings/lockdates"],
  },
  {
    path: "settings/users-roles",
    label: labels.settingsUsersRoles,
    aliases: ["users", "team", "settings/users", "settings/roles"],
  },
  {
    path: "settings/email-domain",
    label: labels.settingsEmailDomain,
    aliases: ["settings/email"],
  },
  {
    path: "settings/subscription",
    label: labels.settingsSubscription,
    aliases: ["subscription", "billing", "settings/billing"],
  },
  { path: "settings/numbering", label: labels.settingsNumbering, aliases: [] },
  { path: "settings/custom-fields", label: labels.settingsCustomFields, aliases: [] },
  {
    path: "settings/audit-log",
    label: labels.settingsAuditLog,
    aliases: ["audit-log", "audit", "history"],
  },
];

/** Module whose path is `path` (exact, lowercase), if any. */
export function findOrgModule(path: string): OrgModule | undefined {
  return ORG_MODULES.find((module) => module.path === path);
}

/** Canonical URL of a module in an organisation. */
export function orgModuleUrl(org: string, modulePath: string): string {
  return `/o/${org}/${modulePath}`;
}

/**
 * URL of the equivalent page in another organisation (A-01-T14 org switcher): the same module, so
 * Contacts stays Contacts and Settings → Lock dates stays Settings → Lock dates. Paths below a
 * module (a record such as `contacts/<id>`) belong to the old organisation, so they land on the
 * module itself; an unknown path lands on Home.
 */
export function equivalentOrgUrl(targetOrg: string, currentPath?: string): string {
  const path = (currentPath ?? "").toLowerCase().replace(/^\/+|\/+$/g, "");
  let best: OrgModule | undefined;
  for (const entry of ORG_MODULES) {
    const matches = path === entry.path || path.startsWith(`${entry.path}/`);
    if (matches && (best === undefined || entry.path.length > best.path.length)) best = entry;
  }
  return orgModuleUrl(targetOrg, best?.path ?? "home");
}

/** Practice directory (V-01): the accountant's list of client organisations. */
export function practiceDirectoryUrl(practice: string): string {
  return `/p/${practice}/directory`;
}
