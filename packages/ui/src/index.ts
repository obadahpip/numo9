/** @numo9/ui public API (A-10). Styles: `@numo9/ui/styles.css`. */
export {
  AppShell,
  Breadcrumbs,
  type AppShellProps,
  type ShellCrumb,
  type ShellLabels,
  type ShellLinkComponent,
  type ShellNavGroup,
  type ShellNavItem,
  type ShellUserMenuItem,
} from "./shell/AppShell";
export {
  OrgSwitcher,
  type OrgSwitcherLabels,
  type OrgSwitcherProps,
  type OrgSwitcherStatus,
  type SwitcherOrg,
} from "./org-switcher/OrgSwitcher";
export {
  normaliseForSearch,
  recentOrganisations,
  searchOrganisations,
} from "./org-switcher/search";
export * from "./primitives";
