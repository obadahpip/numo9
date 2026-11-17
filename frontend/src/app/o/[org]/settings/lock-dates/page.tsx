import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { LockDatesScreen } from "@/settings/general/LockDatesScreen";
import { SettingsLayout } from "@/settings/SettingsLayout";

interface Params {
  org: string;
}

/** Settings → Lock dates (A-05-T13), `/o/:org/settings/lock-dates`. */
export default async function LockDatesPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="settings/lock-dates">
      <SettingsLayout org={org} section="settings/lock-dates">
        <LockDatesScreen org={org} />
      </SettingsLayout>
    </AppShell>
  );
}
