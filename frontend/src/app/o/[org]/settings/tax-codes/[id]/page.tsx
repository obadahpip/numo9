import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { SettingsLayout } from "@/settings/SettingsLayout";
import { TaxCodeEditorPage } from "@/tax/TaxCodeEditorPage";

interface Params {
  org: string;
  id: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Settings → Tax codes → one code (G-01-T13), `/o/:org/settings/tax-codes/:id`. */
export default async function TaxCodePage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !UUID.test(id)) notFound();
  return (
    <AppShell org={org} modulePath="settings/tax-codes">
      <SettingsLayout org={org} section="settings/tax-codes">
        <TaxCodeEditorPage org={org} id={id} />
      </SettingsLayout>
    </AppShell>
  );
}
