import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { SettingsLayout } from "@/settings/SettingsLayout";
import { TaxCodesScreen } from "@/tax/TaxCodesScreen";

interface Params {
  org: string;
}

/** Settings → Tax codes (G-01-T12), `/o/:org/settings/tax-codes`. */
export default async function TaxCodesPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="settings/tax-codes">
      <SettingsLayout org={org} section="settings/tax-codes">
        <TaxCodesScreen org={org} canManage />
      </SettingsLayout>
    </AppShell>
  );
}
