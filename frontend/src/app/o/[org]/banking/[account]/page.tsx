import { notFound } from "next/navigation";

import { BankAccountDetail } from "@/banking/BankAccountDetail";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
  account: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Bank account detail (F-01-T11), `/o/:org/banking/:account`. */
export default async function BankAccountPage({ params }: { params: Promise<Params> }) {
  const { org, account } = await params;
  if (!ORG_SLUG.test(org) || !UUID.test(account)) notFound();
  return (
    <AppShell org={org} modulePath="banking">
      <BankAccountDetail org={org} account={account} />
    </AppShell>
  );
}
