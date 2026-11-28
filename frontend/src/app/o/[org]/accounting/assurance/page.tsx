import { notFound } from "next/navigation";

import { AssuranceScreen } from "@/accounting/assurance/AssuranceScreen";
import { isAssuranceTab } from "@/accounting/assurance/tabs";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/**
 * Accounting → assurance: score, grouped findings and their fixes (K-09-T21/T22), rule settings
 * (K-09-T23) — `?tab=rules` opens a tab directly.
 */
export default async function AssurancePage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const { org } = await params;
  const { tab } = await searchParams;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="accounting/assurance">
      <AssuranceScreen org={org} initialTab={isAssuranceTab(tab) ? tab : "findings"} />
    </AppShell>
  );
}
