import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { SettingsLayout } from "@/settings/SettingsLayout";
import { FilingScreen } from "@/tax/filing/FilingScreen";

interface Params {
  org: string;
  id: string;
}

const UUID = /^[0-9a-f-]{1,64}$/i;

/** Settings → Tax → a registration's filing periods (G-03a-T18…T21). */
export default async function FilingPage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !UUID.test(id)) notFound();
  return (
    <AppShell org={org} modulePath="settings/tax-codes">
      <SettingsLayout org={org} section="settings/tax-codes">
        <FilingScreen org={org} registration={id} canManage />
      </SettingsLayout>
    </AppShell>
  );
}
