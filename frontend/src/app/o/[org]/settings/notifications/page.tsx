import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { NotificationPreferencesScreen } from "@/notifications/NotificationPreferencesScreen";
import { ORG_SLUG } from "@/routing/routes";
import { SettingsLayout } from "@/settings/SettingsLayout";

interface Params {
  org: string;
}

/** Settings → Notifications (A-07-T09), `/o/:org/settings/notifications`: the person's choices. */
export default async function NotificationSettingsPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="settings/notifications">
      <SettingsLayout org={org} section="settings/notifications">
        <NotificationPreferencesScreen org={org} />
      </SettingsLayout>
    </AppShell>
  );
}
