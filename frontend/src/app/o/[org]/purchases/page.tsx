import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { PurchasesOverviewScreen } from "@/purchases/PurchasesOverviewScreen";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Purchases overview (E-02-T15), `/o/:org/purchases` — the shared OverviewPage (gap-22). */
export default async function PurchasesOverviewPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="purchases">
      <PurchasesOverviewScreen org={org} />
    </AppShell>
  );
}
