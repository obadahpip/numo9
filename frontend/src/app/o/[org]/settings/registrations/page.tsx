import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { RegistrationsScreen } from "@/settings/general/RegistrationsScreen";
import { SettingsLayout } from "@/settings/SettingsLayout";

interface Params {
  org: string;
}

/** Settings → Tax registrations (A-05-T12), `/o/:org/settings/registrations`. */
export default async function RegistrationsPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="settings/registrations">
      <SettingsLayout org={org} section="settings/registrations">
        <RegistrationsScreen org={org} />
      </SettingsLayout>
    </AppShell>
  );
}
