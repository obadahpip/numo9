import { notFound } from "next/navigation";

import { CashPolicySettings } from "@/banking/CashPolicySettings";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Banking settings (F-07-T08), `/o/:org/banking/settings`: the negative-balance policy. */
export default async function BankingSettingsPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="banking">
      <CashPolicySettings org={org} />
    </AppShell>
  );
}
