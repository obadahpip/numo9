import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { SettingsLayout } from "@/settings/SettingsLayout";
import { TaxSettingsScreen } from "@/tax/settings/TaxSettingsScreen";

interface Params {
  org: string;
}

/**
 * Settings → Tax registrations and settings, `/o/:org/settings/registrations`: the one tax
 * settings page (G-06-T08), with the registrations repeater of A-05-T12 as its first card.
 */
export default async function RegistrationsPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="settings/registrations">
      <SettingsLayout org={org} section="settings/registrations">
        <TaxSettingsScreen org={org} canManage />
      </SettingsLayout>
    </AppShell>
  );
}
