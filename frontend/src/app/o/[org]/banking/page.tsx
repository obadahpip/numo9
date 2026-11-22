import { notFound } from "next/navigation";

import { BankingHome } from "@/banking/BankingHome";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Banking (F-01-T08), `/o/:org/banking`: bank, credit card, loan and cash accounts. */
export default async function BankingPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="banking">
      <BankingHome org={org} />
    </AppShell>
  );
}
