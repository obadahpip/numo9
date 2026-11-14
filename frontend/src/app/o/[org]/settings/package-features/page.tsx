import { notFound } from "next/navigation";

import { PackageFeaturesScreen } from "@/catalogue/PackageFeaturesScreen";
import { AppShell } from "@/components/AppShell";
import { SettingsLayout } from "@/settings/SettingsLayout";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/**
 * Settings → Package and features (U-01-T12), `/o/:org/settings/package-features`: the in-app
 * feature matrix ("What's in my package"), for everyone in the organisation.
 */
export default async function PackageFeaturesPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="settings/package-features">
      <SettingsLayout org={org} section="settings/package-features">
        <PackageFeaturesScreen org={org} />
      </SettingsLayout>
    </AppShell>
  );
}
