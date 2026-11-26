import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { PurchaseOrderListScreen } from "@/purchases/orders/PurchaseOrderListScreen";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Purchases → purchase orders (E-01-T13), `/o/:org/purchases/orders`: the list with its tabs. */
export default async function PurchaseOrdersPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="purchases/orders">
      <PurchaseOrderListScreen org={org} />
    </AppShell>
  );
}
