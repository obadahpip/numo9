import { notFound } from "next/navigation";
import { Suspense } from "react";

import { BillingScreen } from "@/billing/BillingScreen";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { SettingsLayout } from "@/settings/SettingsLayout";

interface Params {
  org: string;
}

/** Settings → Subscription (U-04-T12), `/o/:org/settings/subscription`: the owner's billing page. */
export default async function SubscriptionPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="settings/subscription">
      <SettingsLayout org={org} section="settings/subscription">
        <Suspense>
          <BillingScreen org={org} />
        </Suspense>
      </SettingsLayout>
    </AppShell>
  );
}
