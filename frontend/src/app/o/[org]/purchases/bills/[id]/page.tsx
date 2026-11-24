import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { BillScreen } from "@/purchases/BillScreen";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
  id: string;
}

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Purchases → one bill (E-02-T11), `/o/:org/purchases/bills/:id`. */
export default async function BillPage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !ID.test(id)) notFound();
  return (
    <AppShell org={org} modulePath="purchases/bills">
      <BillScreen org={org} id={id} />
    </AppShell>
  );
}
