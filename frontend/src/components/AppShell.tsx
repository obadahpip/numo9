"use client";

import { AppShell as Shell, type ShellCrumb, type ShellLinkComponent } from "@numo9/ui";
import Link from "next/link";
import type { ReactNode } from "react";

import { OrgSwitcher } from "@/components/OrgSwitcher";
import { defineMessages, useFormatMessage } from "@/i18n";
import { JobTray } from "@/jobs/JobTray";
import { primaryNav } from "@/routing/navigation";
import { findOrgModule, orgModuleUrl } from "@/routing/routes";

const messages = defineMessages({
  skipToContent: {
    id: "shell.skipToContent",
    defaultMessage: "Skip to content",
    description: "Skip link at the top of every page, jumps to the main content",
  },
  mainNav: {
    id: "shell.nav.main",
    defaultMessage: "Main",
    description: "Accessible name of the main navigation",
  },
  breadcrumbs: {
    id: "shell.breadcrumbs",
    defaultMessage: "Breadcrumbs",
    description: "Accessible name of the breadcrumb trail",
  },
  openMenu: {
    id: "shell.menu.open",
    defaultMessage: "Open navigation",
    description: "Menu button (phones and tablets) that opens the navigation drawer",
  },
  closeMenu: {
    id: "shell.menu.close",
    defaultMessage: "Close navigation",
    description: "Menu button when the navigation drawer is open",
  },
  mobileNav: {
    id: "shell.menu.drawer",
    defaultMessage: "Navigation",
    description: "Accessible name of the navigation drawer (phones and tablets)",
  },
  brandHome: {
    id: "shell.brandHome",
    defaultMessage: "Numo9 home",
    description: "Accessible name of the Numo9 brand mark link in the top bar",
  },
  notifications: {
    id: "shell.notifications",
    defaultMessage: "Notifications",
    description: "Notification bell button in the top bar",
  },
  userMenu: {
    id: "shell.userMenu.label",
    defaultMessage: "Account menu",
    description: "User menu button in the top bar",
  },
  orgSettings: {
    id: "shell.userMenu.orgSettings",
    defaultMessage: "Organisation settings",
    description: "User menu item: opens Settings → General of the current organisation",
  },
  home: {
    id: "routes.home",
    defaultMessage: "Home",
    description: "Module name: organisation home",
  },
});

const NextLink: ShellLinkComponent = ({ href, ...props }) => <Link href={href} {...props} />;

interface AppShellProps {
  /** Active organisation slug (`/o/:org/…`); omitted outside an organisation. */
  org?: string;
  /** Current module path in the route registry, e.g. `accounting/journals`. */
  modulePath?: string;
  children: ReactNode;
}

/**
 * Numo9 application shell (A-10-T05): the `@numo9/ui` shell with i18n labels, the organisation's
 * primary navigation, breadcrumbs, the org switcher (A-01-T14) and the job tray (A-08-T07). The
 * notification centre (A-07), command palette (A-09), practice navigation (V-01) and the
 * signed-in user (A-02) plug into the shell's slots as those deliverables land.
 */
export function AppShell({ org, modulePath, children }: Readonly<AppShellProps>) {
  const fm = useFormatMessage();
  const entry = modulePath === undefined ? undefined : findOrgModule(modulePath);
  const homeHref = org ? orgModuleUrl(org, "home") : "/";

  const breadcrumbs: ShellCrumb[] = [];
  if (org) breadcrumbs.push({ label: org, href: homeHref });
  breadcrumbs.push({ label: fm(entry?.label ?? messages.home) });

  return (
    <Shell
      labels={{
        skipToContent: fm(messages.skipToContent),
        primaryNav: fm(messages.mainNav),
        breadcrumbs: fm(messages.breadcrumbs),
        openMenu: fm(messages.openMenu),
        closeMenu: fm(messages.closeMenu),
        mobileNav: fm(messages.mobileNav),
      }}
      brand={{ label: fm(messages.brandHome), href: homeHref }}
      nav={org ? primaryNav(fm, org, modulePath) : []}
      breadcrumbs={breadcrumbs}
      orgSwitcher={
        org ? (
          <OrgSwitcher org={org} modulePath={entry?.path} linkComponent={NextLink} />
        ) : undefined
      }
      jobTray={org ? <JobTray org={org} /> : undefined}
      notifications={{ label: fm(messages.notifications) }}
      user={{
        label: fm(messages.userMenu),
        items: org
          ? [
              {
                id: "org-settings",
                label: fm(messages.orgSettings),
                href: orgModuleUrl(org, "settings/general"),
              },
            ]
          : [],
      }}
      linkComponent={NextLink}
    >
      {children}
    </Shell>
  );
}
