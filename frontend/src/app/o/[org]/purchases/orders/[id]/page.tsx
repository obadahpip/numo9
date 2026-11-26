import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { PurchaseOrderScreen } from "@/purchases/orders/PurchaseOrderScreen";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
  id: string;
}

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Purchases → one purchase order (E-01-T11), `/o/:org/purchases/orders/:id`. */
export default async function PurchaseOrderPage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !ID.test(id)) notFound();
  return (
    <AppShell org={org} modulePath="purchases/orders">
      <PurchaseOrderScreen org={org} id={id} />
    </AppShell>
  );
}
