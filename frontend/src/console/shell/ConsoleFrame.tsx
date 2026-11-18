"use client";

/**
 * Platform console frame (U-06-T02): every `/console/*` page renders inside it. It is the route
 * guard — it asks `GET /api/v1/platform/me` first and shows the console only to platform staff
 * with two-factor authentication: anyone else sees the **404 page** (the console doesn't exist for
 * them, nothing leaks), a platform user without 2FA is sent to set it up. Then the console's own
 * navigation, on the console's accent bar (distinct from any organisation, so staff never confuse
 * the two), with the areas their permissions open.
 */
import { BUTTON_BASE, ExplainPanel } from "@numo9/ui";
import Link from "next/link";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { defineMessages, useFormatMessage, type MessageDescriptor } from "@/i18n";

import { getPlatformMe, type PlatformMe } from "./api";

const messages = defineMessages({
  nav: {
    id: "console.shell.nav",
    defaultMessage: "Platform console",
    description: "Accessible name of the console navigation; also its visible label",
  },
  metrics: { id: "console.shell.metrics", defaultMessage: "Metrics", description: "Console nav" },
  practices: {
    id: "console.shell.practices",
    defaultMessage: "Practices",
    description: "Console nav",
  },
  organisations: {
    id: "console.shell.organisations",
    defaultMessage: "Organisations",
    description: "Console nav",
  },
  packages: {
    id: "console.shell.packages",
    defaultMessage: "Packages and prices",
    description: "Console nav",
  },
  flags: { id: "console.shell.flags", defaultMessage: "Feature flags", description: "Console nav" },
  jobs: { id: "console.shell.jobs", defaultMessage: "Jobs", description: "Console nav" },
  loading: {
    id: "console.shell.loading",
    defaultMessage: "Opening the console…",
    description: "While the console checks who is signed in",
  },
  notFoundTitle: {
    id: "console.shell.notFoundTitle",
    defaultMessage: "We can't find that page",
    description: "The console's 404 for anyone who isn't platform staff",
  },
  notFoundBody: {
    id: "console.shell.notFoundBody",
    defaultMessage:
      "The address may be mistyped, or the page may have moved. Search for the page or go to Home.",
    description: "Explanation on the console's 404",
  },
  home: { id: "console.shell.home", defaultMessage: "Go to Home", description: "Link Home" },
  twoFactorTitle: {
    id: "console.shell.twoFactorTitle",
    defaultMessage: "Turn on two-factor authentication",
    description: "Console refused: 2FA required",
  },
  twoFactorBody: {
    id: "console.shell.twoFactorBody",
    defaultMessage: "The platform console needs two-factor authentication. It takes a minute.",
    description: "Console refused: 2FA required",
  },
  twoFactorAction: {
    id: "console.shell.twoFactorAction",
    defaultMessage: "Set it up",
    description: "Link to Security settings",
  },
});

interface Area {
  href: string;
  label: MessageDescriptor;
  permission: string;
}

export const CONSOLE_AREAS: Area[] = [
  { href: "/console", label: messages.metrics, permission: "platform.console.view" },
  { href: "/console/practices", label: messages.practices, permission: "platform.console.view" },
  {
    href: "/console/organisations",
    label: messages.organisations,
    permission: "platform.console.view",
  },
  { href: "/console/packages", label: messages.packages, permission: "platform.catalogue.manage" },
  { href: "/console/flags", label: messages.flags, permission: "platform.flags.manage" },
  { href: "/console/jobs", label: messages.jobs, permission: "platform.jobs.view" },
];

const MeContext = createContext<PlatformMe | null>(null);

/** The signed-in platform user (inside `ConsoleFrame`). */
export function usePlatformMe(): PlatformMe | null {
  return useContext(MeContext);
}

export interface ConsoleFrameProps {
  /** The current console path (`/console/organisations`…), for the active nav item. */
  current: string;
  children: ReactNode;
}

export function ConsoleFrame({ current, children }: ConsoleFrameProps) {
  const fm = useFormatMessage();
  const [state, setState] = useState<"loading" | "ok" | "missing" | "two_factor">("loading");
  const [me, setMe] = useState<PlatformMe | null>(null);
  useEffect(() => {
    let cancelled = false;
    void getPlatformMe().then((result) => {
      if (cancelled) return;
      if (result.status === 200) {
        setMe(result.body);
        setState("ok");
      } else if (
        result.status === 403 &&
        (result.body as { code?: string } | null)?.code === "auth.two_factor_required"
      ) {
        setState("two_factor");
      } else {
        setState("missing");
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "loading") {
    return <p className="text-sm text-fg-muted">{fm(messages.loading)}</p>;
  }
  if (state === "missing") {
    return (
      <ExplainPanel
        kind="notFound"
        headingLevel={1}
        title={fm(messages.notFoundTitle)}
        body={fm(messages.notFoundBody)}
        actions={[
          <Link
            key="home"
            href="/"
            className={`${BUTTON_BASE} min-h-touch-target border border-border-strong px-4 text-sm`}
          >
            {fm(messages.home)}
          </Link>,
        ]}
      />
    );
  }
  if (state === "two_factor") {
    return (
      <ExplainPanel
        kind="permission"
        headingLevel={1}
        title={fm(messages.twoFactorTitle)}
        body={fm(messages.twoFactorBody)}
        actions={[
          <Link
            key="2fa"
            href="/account/security"
            className={`${BUTTON_BASE} min-h-touch-target border border-border-strong px-4 text-sm`}
          >
            {fm(messages.twoFactorAction)}
          </Link>,
        ]}
      />
    );
  }
  const allowed = new Set(me?.permissions ?? []);
  return (
    <MeContext.Provider value={me}>
      <div className="flex flex-col gap-4" data-console="">
        <nav
          aria-label={fm(messages.nav)}
          className="-mx-4 -mt-4 flex flex-wrap items-center gap-1 border-b-4 border-[#7CC4FF] bg-[#0B2540] px-4 py-2 md:-mx-6 md:px-6"
        >
          <span className="me-3 text-sm font-bold text-white">{fm(messages.nav)}</span>
          {CONSOLE_AREAS.filter((area) => allowed.has(area.permission)).map((area) => {
            const active =
              area.href === "/console" ? current === "/console" : current.startsWith(area.href);
            return (
              <Link
                key={area.href}
                href={area.href}
                aria-current={active ? "page" : undefined}
                className={`rounded px-3 py-1 text-sm font-semibold ${
                  active
                    ? "bg-[#7CC4FF] text-[#0B2540]"
                    : "text-white underline-offset-2 hover:underline"
                }`}
              >
                {fm(area.label)}
              </Link>
            );
          })}
        </nav>
        {children}
      </div>
    </MeContext.Provider>
  );
}
