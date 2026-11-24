import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { BillScreen } from "@/purchases/BillScreen";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * New bill (E-02-T11), `/o/:org/purchases/bills/new` — `?document=<id>` opens it beside the
 * document from the inbox's "Create a bill" (A-06-T11).
 */
export default async function NewBillPage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<{ document?: string }>;
}) {
  const { org } = await params;
  const { document } = await searchParams;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="purchases/bills">
      <BillScreen org={org} documentId={document && ID.test(document) ? document : null} />
    </AppShell>
  );
}
