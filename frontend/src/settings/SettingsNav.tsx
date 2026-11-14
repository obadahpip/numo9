"use client";

import Link from "next/link";

import { cn } from "@numo9/ui";

import { defineMessages, useFormatMessage } from "@/i18n";
import { orgModuleUrl, SETTINGS_LABEL, settingsSections } from "@/routing/routes";

const messages = defineMessages({
  navLabel: {
    id: "settings.nav.label",
    defaultMessage: "Settings sections",
    description: "Accessible name of the settings navigation (left column of every settings page)",
  },
});

interface SettingsNavProps {
  org: string;
  /** The section shown (`settings/lock-dates`); marked as the current page. */
  current: string;
}

/**
 * Settings navigation (A-05-T10, wireframe 04-settings): every settings section as a deep link
 * `/o/:org/settings/<section>`, in the registry's order, the current one marked. A left column
 * from 768 px; above the content as a wrapping list on phones.
 */
export function SettingsNav({ org, current }: Readonly<SettingsNavProps>) {
  const fm = useFormatMessage();
  return (
    <nav aria-label={fm(messages.navLabel)} data-settings-nav="">
      <p className="mb-2 text-xs font-semibold tracking-wide text-fg-muted uppercase" aria-hidden>
        {fm(SETTINGS_LABEL)}
      </p>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 md:flex-col md:gap-0">
        {settingsSections().map((section) => {
          const isCurrent = section.path === current;
          return (
            <li key={section.path}>
              <Link
                href={orgModuleUrl(org, section.path)}
                aria-current={isCurrent ? "page" : undefined}
                className={cn(
                  "inline-flex min-h-touch-target items-center rounded-md text-sm md:flex md:px-3",
                  isCurrent
                    ? "font-semibold text-fg md:bg-surface-muted"
                    : "text-fg-muted hover:text-fg md:hover:bg-surface-muted",
                )}
              >
                {fm(section.sectionLabel ?? section.label)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
