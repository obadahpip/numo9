import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ReceiveScreen } from "@/purchases/orders/ReceiveScreen";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
  id: string;
}

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Purchases → receive goods against a purchase order (E-01-T12). */
export default async function ReceivePage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !ID.test(id)) notFound();
  return (
    <AppShell org={org} modulePath="purchases/orders">
      <ReceiveScreen org={org} id={id} />
    </AppShell>
  );
}
