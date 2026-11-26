import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { PurchaseOrderScreen } from "@/purchases/orders/PurchaseOrderScreen";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** New purchase order (E-01-T11), `/o/:org/purchases/orders/new` (quick-create N P). */
export default async function NewPurchaseOrderPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="purchases/orders">
      <PurchaseOrderScreen org={org} />
    </AppShell>
  );
}
