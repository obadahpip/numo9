import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { SettingsLayout } from "@/settings/SettingsLayout";
import { TaxCodeEditor } from "@/tax/TaxCodeEditor";

interface Params {
  org: string;
}

/** Settings → Tax codes → New (G-01-T13), `/o/:org/settings/tax-codes/new?side=sales`. */
export default async function NewTaxCodePage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<{ side?: string }>;
}) {
  const { org } = await params;
  const { side } = await searchParams;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="settings/tax-codes">
      <SettingsLayout org={org} section="settings/tax-codes">
        <TaxCodeEditor org={org} side={side === "purchase" ? "purchase" : "sales"} />
      </SettingsLayout>
    </AppShell>
  );
}
