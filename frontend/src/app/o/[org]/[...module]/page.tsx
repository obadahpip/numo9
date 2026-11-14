import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";
import { findOrgModule, isSettingsSection, ORG_SLUG } from "@/routing/routes";
import { SettingsLayout } from "@/settings/SettingsLayout";

const messages = defineMessages({
  placeholder: {
    id: "routes.placeholder",
    defaultMessage: "This screen is a placeholder until its deliverable is built.",
    description:
      "Body text of an organisation module that exists in the route map but not yet as a screen",
  },
});

interface Params {
  org: string;
  module: string[];
}

/**
 * Canonical organisation module URL `/o/:org/<module>` (S-01-T14). Renders a placeholder for every
 * module in the route registry; unknown modules and invalid slugs get the custom 404. Each module's
 * deliverable replaces its placeholder with the real screen. Settings sections sit in the settings
 * frame (navigation on the left, A-05-T10).
 */
export default async function OrganisationModulePage({ params }: { params: Promise<Params> }) {
  const { org, module } = await params;
  const entry = findOrgModule(module.join("/"));
  if (!ORG_SLUG.test(org) || entry === undefined) notFound();
  const fm = await getFormatMessage();

  const body = (
    <>
      <h1 className="text-2xl font-semibold">{fm(entry.label)}</h1>
      <p className="mt-2 text-sm text-fg-muted">{fm(messages.placeholder)}</p>
    </>
  );
  return (
    <AppShell org={org} modulePath={entry.path}>
      {isSettingsSection(entry.path) ? (
        <SettingsLayout org={org} section={entry.path}>
          {body}
        </SettingsLayout>
      ) : (
        body
      )}
    </AppShell>
  );
}
