/**
 * Route registry (S-01-T14): the canonical organisation-app URLs that exist today and the
 * legacy-style aliases that redirect to them. Later deliverables add their modules here so the
 * redirect map, the 404 page search and the `gap-02` crawler stay in step with the real routes.
 *
 * URL scheme (Phase 0 information architecture): `/o/:org/<module>`, e.g. `/o/acme/home`.
 */
import { CORE, type FeatureDeclaration } from "@/catalogue/features";
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
  settingsPackageFeatures: {
    id: "routes.settingsPackageFeatures",
    defaultMessage: "Settings: Package and features",
    description: "Settings section: what each package includes (feature matrix)",
  },
});

const sectionLabels = defineMessages({
  settings: {
    id: "settings.nav.settings",
    defaultMessage: "Settings",
    description: "Settings navigation heading and breadcrumb (organisation settings)",
  },
  general: {
    id: "settings.nav.general",
    defaultMessage: "General",
    description: "Settings section",
  },
  registrations: {
    id: "settings.nav.registrations",
    defaultMessage: "Tax registrations",
    description: "Settings section: BN, GST/HST, QST registrations",
  },
  lockDates: {
    id: "settings.nav.lockDates",
    defaultMessage: "Lock dates",
    description: "Settings section",
  },
  usersRoles: {
    id: "settings.nav.usersRoles",
    defaultMessage: "Users and roles",
    description: "Settings section",
  },
  emailDomain: {
    id: "settings.nav.emailDomain",
    defaultMessage: "Email domain",
    description: "Settings section",
  },
  subscription: {
    id: "settings.nav.subscription",
    defaultMessage: "Subscription",
    description: "Settings section",
  },
  numbering: {
    id: "settings.nav.numbering",
    defaultMessage: "Numbering",
    description: "Settings section: document number patterns",
  },
  customFields: {
    id: "settings.nav.customFields",
    defaultMessage: "Custom fields",
    description: "Settings section",
  },
  auditLog: {
    id: "settings.nav.auditLog",
    defaultMessage: "Audit log",
    description: "Settings section",
  },
  packageFeatures: {
    id: "settings.nav.packageFeatures",
    defaultMessage: "Package and features",
    description: "Settings section: what each package includes (feature matrix)",
  },
});

/** Heading of the settings navigation and middle breadcrumb of every settings page. */
export const SETTINGS_LABEL = sectionLabels.settings;

/** Path prefix of the organisation settings sections. */
export const SETTINGS_PREFIX = "settings/";

export interface OrgModule {
  /** Path below `/o/:org/`, lowercase, no leading or trailing slash. */
  path: string;
  label: MessageDescriptor;
  /**
   * Legacy-style paths (lowercase, no leading slash) that land on this module: Numo9 short
   * forms, common words and the Xero URLs Profitex staff have bookmarked (teardown §0–§6).
   */
  aliases: readonly string[];
  /**
   * Feature key the module needs (`accounting.journals.read`), or `CORE` when every organisation
   * has it — the entitlement engine (U-03) gates the route from this; eslint
   * `numo9/route-feature` requires it on every entry (U-01-T08).
   */
  feature: FeatureDeclaration;
  /**
   * Settings sections (`settings/…`) only: the section's name in the settings navigation and the
   * breadcrumb ("Lock dates"), where `label` is the full name ("Settings: Lock dates").
   */
  sectionLabel?: MessageDescriptor;
  /**
   * Modules only: the settings section that configures this module — the module's gear links
   * there (A-05-T10, gap-03: never one generic settings page for every module).
   */
  settings?: string;
}

export const ORG_MODULES: readonly OrgModule[] = [
  {
    path: "home",
    feature: CORE,
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
    feature: "accounting.contacts.read",
    label: labels.contacts,
    settings: "settings/custom-fields",
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
    feature: "accounting.chart_of_accounts.read",
    label: labels.chartOfAccounts,
    settings: "settings/general",
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
    feature: "accounting.journals.read",
    label: labels.journals,
    settings: "settings/lock-dates",
    aliases: ["journals", "journal", "manual-journals", "journal/search.aspx"],
  },
  {
    path: "documents",
    feature: "accounting.documents.read",
    label: labels.documents,
    aliases: ["document", "files", "inbox"],
  },
  {
    path: "settings/general",
    feature: CORE,
    label: labels.settingsGeneral,
    sectionLabel: sectionLabels.general,
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
    feature: CORE,
    label: labels.settingsRegistrations,
    sectionLabel: sectionLabels.registrations,
    aliases: ["settings/tax", "tax-settings", "registrations"],
  },
  {
    path: "settings/lock-dates",
    feature: CORE,
    label: labels.settingsLockDates,
    sectionLabel: sectionLabels.lockDates,
    aliases: ["lock-dates", "settings/lockdates"],
  },
  {
    path: "settings/users-roles",
    feature: CORE,
    label: labels.settingsUsersRoles,
    sectionLabel: sectionLabels.usersRoles,
    aliases: ["users", "team", "settings/users", "settings/roles"],
  },
  {
    path: "settings/email-domain",
    feature: CORE,
    label: labels.settingsEmailDomain,
    sectionLabel: sectionLabels.emailDomain,
    aliases: ["settings/email"],
  },
  {
    path: "settings/subscription",
    feature: CORE,
    label: labels.settingsSubscription,
    sectionLabel: sectionLabels.subscription,
    aliases: ["subscription", "billing", "settings/billing"],
  },
  {
    path: "settings/numbering",
    feature: CORE,
    label: labels.settingsNumbering,
    sectionLabel: sectionLabels.numbering,
    aliases: [],
  },
  {
    path: "settings/custom-fields",
    label: labels.settingsCustomFields,
    sectionLabel: sectionLabels.customFields,
    aliases: [],
    feature: CORE,
  },
  {
    path: "settings/audit-log",
    feature: CORE,
    label: labels.settingsAuditLog,
    sectionLabel: sectionLabels.auditLog,
    aliases: ["audit-log", "audit", "history"],
  },
  {
    path: "settings/package-features",
    feature: CORE,
    label: labels.settingsPackageFeatures,
    sectionLabel: sectionLabels.packageFeatures,
    aliases: ["package", "packages", "plans", "features", "feature-matrix", "settings/package"],
  },
];

/** Is the module path a settings section (`settings/general`…)? */
export function isSettingsSection(path: string): boolean {
  return path.startsWith(SETTINGS_PREFIX);
}

/** The settings sections in navigation order (the registry's order, wireframe 04-settings). */
export function settingsSections(): OrgModule[] {
  return ORG_MODULES.filter((module) => isSettingsSection(module.path));
}

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
