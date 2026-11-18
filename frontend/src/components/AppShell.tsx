"use client";

import { AppShell as Shell, type ShellCrumb, type ShellLinkComponent } from "@numo9/ui";
import Link from "next/link";
import { useState, type ReactNode } from "react";

import { CORE } from "@/catalogue/features";
import { Gated } from "@/catalogue/Gated";
import { OrgSwitcher } from "@/components/OrgSwitcher";
import { ImpersonationBar } from "@/console/impersonation/ImpersonationBar";
import { TrialChip } from "@/entitlements/TrialChip";
import { PaymentDueNotice } from "@/entitlements/PaymentDueNotice";
import { ReadOnlyNotice } from "@/entitlements/ReadOnlyNotice";
import { GoToOrganisationSlot } from "@/directory/GoToOrganisationSlot";
import { decide, EntitlementsProvider, useEntitlements } from "@/entitlements/store";
import { defineMessages, useFormatMessage } from "@/i18n";
import { JobTray } from "@/jobs/JobTray";
import {
  centreMessages,
  NotificationCentre,
  UnreadAnnouncer,
} from "@/notifications/NotificationCentre";
import { useUnreadCount } from "@/notifications/useUnreadCount";
import { primaryNav } from "@/routing/navigation";
import {
  findOrgModule,
  isSettingsSection,
  orgModuleUrl,
  practiceDirectoryUrl,
  SETTINGS_LABEL,
} from "@/routing/routes";
import { ModuleSettingsLink } from "@/settings/ModuleSettingsLink";

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
  /** Breadcrumb of a page outside the organisation registry (platform console, A-08-T08). */
  section?: string;
  /** Practice public id of a practice page (`/p/:practice/…`, the directory V-01). */
  practice?: string;
  children: ReactNode;
}

/**
 * Numo9 application shell (A-10-T05): the `@numo9/ui` shell with i18n labels, the organisation's
 * primary navigation, breadcrumbs, the org switcher (A-01-T14), the job tray (A-08-T07) and the
 * notification bell + centre (A-07-T09). The command palette (A-09), practice navigation (V-01) and the
 * signed-in user (A-02) plug into the shell's slots as those deliverables land. A module with its
 * own settings section shows its gear at the end of the breadcrumb bar (A-05-T10, gap-03);
 * settings pages read Organisation / Settings / <section>.
 *
 * Entitlements (U-03-T10…T12): inside an organisation the shell mounts the entitlement store, so
 * every `<Gated>` below decides from the organisation's package; navigation items of gated
 * modules show a lock glyph; a gated module renders its locked panel at its own URL (never a
 * redirect, gap-14); a read-only organisation gets the read-only notice under the top navigation.
 */
export function AppShell(props: Readonly<AppShellProps>) {
  if (!props.org) return <ShellFrame {...props} />;
  return (
    <EntitlementsProvider org={props.org}>
      <ShellFrame {...props} />
    </EntitlementsProvider>
  );
}

function ShellFrame({ org, modulePath, section, practice, children }: Readonly<AppShellProps>) {
  const fm = useFormatMessage();
  const entitlements = useEntitlements();
  const unread = useUnreadCount(org);
  const [centreOpen, setCentreOpen] = useState(false);
  const entry = modulePath === undefined ? undefined : findOrgModule(modulePath);
  const homeHref = org
    ? orgModuleUrl(org, "home")
    : practice
      ? practiceDirectoryUrl(practice)
      : "/";

  const breadcrumbs: ShellCrumb[] = [];
  if (org) breadcrumbs.push({ label: org, href: homeHref });
  if (org && entry && isSettingsSection(entry.path)) {
    // Organisation / Settings / Lock dates (wireframe 04-settings).
    breadcrumbs.push({ label: fm(SETTINGS_LABEL), href: orgModuleUrl(org, "settings/general") });
    breadcrumbs.push({ label: fm(entry.sectionLabel ?? entry.label) });
  } else {
    breadcrumbs.push({ label: section ?? fm(entry?.label ?? messages.home) });
  }

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
      nav={org ? primaryNav(fm, org, modulePath, (key) => decide(entitlements, key)) : []}
      banner={
        <>
          {/* U-06-T11: the red support-session bar, on every page while impersonating. */}
          <ImpersonationBar />
          {org ? (
            <>
              <ReadOnlyNotice />
              <PaymentDueNotice />
            </>
          ) : null}
        </>
      }
      breadcrumbs={breadcrumbs}
      orgSwitcher={
        org ? (
          <OrgSwitcher org={org} modulePath={entry?.path} linkComponent={NextLink} />
        ) : undefined
      }
      jobTray={org ? <JobTray org={org} /> : undefined}
      search={org || practice ? <GoToOrganisationSlot practice={practice} org={org} /> : undefined}
      status={
        org ? (
          <>
            <TrialChip />
            {entry?.settings ? (
              <ModuleSettingsLink org={org} module={entry} linkComponent={NextLink} />
            ) : null}
          </>
        ) : undefined
      }
      notifications={
        org
          ? {
              label: fm(centreMessages.bell, { count: unread.count ?? 0 }),
              count: unread.count ?? 0,
              onOpen: () => setCentreOpen(true),
            }
          : { label: fm(messages.notifications) }
      }
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
      {org ? (
        <>
          <NotificationCentre
            org={org}
            open={centreOpen}
            onOpenChange={setCentreOpen}
            onCount={unread.set}
          />
          <UnreadAnnouncer count={unread.count} />
        </>
      ) : null}
      {org && entry && entry.feature !== CORE ? (
        // The module's own feature key: its locked panel in place, the URL unchanged (gap-14).
        <Gated feature={entry.feature} headingLevel={1}>
          {children}
        </Gated>
      ) : (
        children
      )}
    </Shell>
  );
}
