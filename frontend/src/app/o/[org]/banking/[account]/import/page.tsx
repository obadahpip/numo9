import { notFound } from "next/navigation";

import { StatementImportScreen } from "@/banking/statements/StatementImportWizard";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
  account: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Statement import wizard (F-02-T12), `/o/:org/banking/:account/import`. */
export default async function StatementImportPage({ params }: { params: Promise<Params> }) {
  const { org, account } = await params;
  if (!ORG_SLUG.test(org) || !UUID.test(account)) notFound();
  return (
    <AppShell org={org} modulePath="banking">
      <StatementImportScreen org={org} account={account} />
    </AppShell>
  );
}
