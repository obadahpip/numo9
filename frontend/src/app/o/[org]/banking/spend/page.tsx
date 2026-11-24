import { notFound } from "next/navigation";

import { MoneyForm } from "@/banking/MoneyForm";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Spend money (F-01-T10), `/o/:org/banking/spend?account=<bank account>`. */
export default async function SpendMoneyPage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<{ account?: string }>;
}) {
  const { org } = await params;
  const { account } = await searchParams;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="banking">
      <MoneyForm org={org} kind="spend" account={account && UUID.test(account) ? account : null} />
    </AppShell>
  );
}
