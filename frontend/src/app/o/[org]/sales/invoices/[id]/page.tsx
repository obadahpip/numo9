import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { InvoiceScreen } from "@/sales/invoices/InvoiceScreen";

interface Params {
  org: string;
  id: string;
}

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Sales → one invoice (D-03a-T13), `/o/:org/sales/invoices/:id`. */
export default async function InvoicePage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !ID.test(id)) notFound();
  return (
    <AppShell org={org}>
      <InvoiceScreen org={org} id={id} />
    </AppShell>
  );
}
