"use client";

import type { ShellLinkComponent } from "@numo9/ui";

import { defineMessages, useFormatMessage } from "@/i18n";
import { findOrgModule, orgModuleUrl, type OrgModule } from "@/routing/routes";

const messages = defineMessages({
  label: {
    id: "settings.moduleGear.label",
    defaultMessage: "{module} settings",
    description:
      "Gear link at the end of the breadcrumb bar of a module; opens that module's own settings " +
      "section. {module} is the module name, e.g. Contacts",
  },
});

function GearIcon() {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
    </svg>
  );
}

interface ModuleSettingsLinkProps {
  org: string;
  /** The module whose gear this is; must have a `settings` section in the route registry. */
  module: OrgModule;
  linkComponent: ShellLinkComponent;
}

/**
 * The module's gear (A-05-T10, gap-03): opens the settings section that configures this module —
 * Contacts → Custom fields, Journals → Lock dates — never one generic settings page.
 */
export function ModuleSettingsLink({
  org,
  module,
  linkComponent: Link,
}: Readonly<ModuleSettingsLinkProps>) {
  const fm = useFormatMessage();
  const section = module.settings === undefined ? undefined : findOrgModule(module.settings);
  if (section === undefined) return null;
  const label = fm(messages.label, { module: fm(module.label) });
  return (
    <Link
      href={orgModuleUrl(org, section.path)}
      aria-label={label}
      title={label}
      data-module-settings={section.path}
      className="inline-flex size-touch-target items-center justify-center rounded-md text-fg-muted hover:bg-surface-muted hover:text-fg"
    >
      <GearIcon />
    </Link>
  );
}
