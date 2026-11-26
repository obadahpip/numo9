import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { isBillTab } from "@/purchases/api";
import { BillsListScreen } from "@/purchases/BillsListScreen";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Bills list (E-02-T15), `/o/:org/purchases/bills?tab=overdue` — tabs with the overview's counts. */
export default async function BillsListPage({
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
    <AppShell org={org} modulePath="purchases/bills">
      <BillsListScreen org={org} initialTab={isBillTab(tab) ? tab : "all"} />
    </AppShell>
  );
}
