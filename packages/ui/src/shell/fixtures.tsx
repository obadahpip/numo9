import type { AppShellProps } from "./AppShell";

/** Sample shell props (Canadian sample data) shared by the stories and the tests. */
export const sampleShell: Omit<AppShellProps, "children"> = {
  labels: {
    skipToContent: "Skip to content",
    primaryNav: "Main",
    breadcrumbs: "Breadcrumbs",
    openMenu: "Open navigation",
    closeMenu: "Close navigation",
    mobileNav: "Navigation",
  },
  brand: { label: "Numo9 — Home", href: "/o/maple-leaf/home" },
  nav: [
    { id: "home", label: "Home", href: "/o/maple-leaf/home", current: true },
    { id: "contacts", label: "Contacts", href: "/o/maple-leaf/contacts" },
    { id: "accounting", label: "Accounting", href: "/o/maple-leaf/accounting/chart-of-accounts" },
    { id: "documents", label: "Documents", href: "/o/maple-leaf/documents" },
    { id: "settings", label: "Settings", href: "/o/maple-leaf/settings/general" },
  ],
  practiceNav: {
    label: "Practice",
    items: [
      { id: "directory", label: "Directory", href: "/p/abuodeh-cpa/directory" },
      { id: "dashboard", label: "Dashboard", href: "/p/abuodeh-cpa/dashboard" },
    ],
  },
  breadcrumbs: [
    { label: "Abuodeh CPA", href: "/p/abuodeh-cpa/directory" },
    { label: "Maple Leaf Supply Ltd.", href: "/o/maple-leaf/home" },
    { label: "Home" },
  ],
  notifications: { label: "Notifications, 3 unread", count: 3 },
  user: {
    label: "Account menu: Dana Lee",
    name: "Dana Lee",
    initials: "DL",
    items: [
      { id: "profile", label: "Profile", href: "/me/profile" },
      { id: "preferences", label: "Preferences", href: "/me/preferences" },
      { id: "logout", label: "Log out" },
    ],
  },
};
