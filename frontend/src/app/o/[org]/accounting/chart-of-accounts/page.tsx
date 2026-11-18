import { notFound } from "next/navigation";

import { ChartScreen } from "@/accounts/ChartScreen";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Accounting → Chart of accounts (C-01-T11, T12), `/o/:org/accounting/chart-of-accounts`. */
export default async function ChartOfAccountsPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="accounting/chart-of-accounts">
      <ChartScreen org={org} />
    </AppShell>
  );
}
