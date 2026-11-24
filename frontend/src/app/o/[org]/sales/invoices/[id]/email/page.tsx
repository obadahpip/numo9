import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { InvoiceEmailComposer } from "@/sales/InvoiceEmailComposer";

interface Params {
  org: string;
  id: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Invoice email composer (D-03a-T15), `/o/:org/sales/invoices/:id/email`. */
export default async function InvoiceEmailPage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !UUID.test(id)) notFound();
  return (
    <AppShell org={org}>
      <InvoiceEmailComposer org={org} id={id} />
    </AppShell>
  );
}
