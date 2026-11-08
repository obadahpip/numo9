/**
 * gap-02 crawl list (S-01-T14): root, `/o/:org` and legacy-style URLs (case, trailing slash,
 * Xero bookmarks, typos). Each must end on a 200 page at `final` — never a 404.
 * `org` sets the current-organisation cookie for that request.
 */
export interface CrawlPath {
  path: string;
  final: string;
  org?: string;
}

const ORG = "acme";

export const GAP_02_PATHS: readonly CrawlPath[] = [
  // Root and legacy paths without a current organisation → Home "/"
  { path: "/", final: "/" },
  { path: "/home", final: "/" },
  { path: "/HOME", final: "/" },
  { path: "/home/", final: "/" },
  { path: "/dashboard", final: "/" },
  { path: "/Dashboard/", final: "/" },
  { path: "/settings", final: "/" },
  { path: "/settings/", final: "/" },
  { path: "/Settings", final: "/" },
  { path: "/homepage", final: "/" },
  // Legacy paths with a current organisation → that organisation's module
  { path: "/home", org: ORG, final: "/o/acme/home" },
  { path: "/dashboard", org: ORG, final: "/o/acme/home" },
  { path: "/DASHBOARD/", org: ORG, final: "/o/acme/home" },
  { path: "/settings", org: ORG, final: "/o/acme/settings/general" },
  { path: "/Settings/", org: ORG, final: "/o/acme/settings/general" },
  { path: "/settings/tax", org: ORG, final: "/o/acme/settings/registrations" },
  { path: "/contacts", org: ORG, final: "/o/acme/contacts" },
  { path: "/chart-of-accounts", org: ORG, final: "/o/acme/accounting/chart-of-accounts" },
  { path: "/journals", org: ORG, final: "/o/acme/accounting/journals" },
  { path: "/documents", org: ORG, final: "/o/acme/documents" },
  {
    path: "/GeneralLedger/ChartOfAccounts.aspx",
    org: ORG,
    final: "/o/acme/accounting/chart-of-accounts",
  },
  { path: "/Journal/Search.aspx", org: ORG, final: "/o/acme/accounting/journals" },
  { path: "/Setup/FinancialSettings.aspx", org: ORG, final: "/o/acme/settings/general" },
  { path: "/default.aspx", org: ORG, final: "/o/acme/home" },
  { path: "/dashbaord", org: ORG, final: "/o/acme/home" },
  { path: "/setings", org: ORG, final: "/o/acme/settings/general" },
  // Organisation-scoped
  { path: "/o/acme", final: "/o/acme/home" },
  { path: "/o/acme/", final: "/o/acme/home" },
  { path: "/O/ACME", final: "/o/acme/home" },
  { path: "/o/acme/home", final: "/o/acme/home" },
  { path: "/o/acme/Home/", final: "/o/acme/home" },
  { path: "/o/acme/dashboard", final: "/o/acme/home" },
  { path: "/o/acme/settings", final: "/o/acme/settings/general" },
  { path: "/o/acme/settings/", final: "/o/acme/settings/general" },
  { path: "/o/acme/Settings/General", final: "/o/acme/settings/general" },
  { path: "/o/acme/accounting", final: "/o/acme/accounting/chart-of-accounts" },
  { path: "/o/acme/contacts/", final: "/o/acme/contacts" },
  { path: "/o/acme/settings/tax", final: "/o/acme/settings/registrations" },
  { path: "/o/acme/homepage", final: "/o/acme/home" },
  { path: "/o/acme/settings/lock-dates", final: "/o/acme/settings/lock-dates" },
];
