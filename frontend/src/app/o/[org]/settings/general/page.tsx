import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { GeneralSettingsScreen } from "@/settings/general/GeneralSettingsScreen";
import { SettingsLayout } from "@/settings/SettingsLayout";

interface Params {
  org: string;
}

/** Settings → General (A-05-T11), `/o/:org/settings/general`. */
export default async function GeneralSettingsPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="settings/general">
      <SettingsLayout org={org} section="settings/general">
        <GeneralSettingsScreen org={org} />
      </SettingsLayout>
    </AppShell>
  );
}
