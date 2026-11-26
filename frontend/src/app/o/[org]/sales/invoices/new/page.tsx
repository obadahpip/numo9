import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { InvoiceScreen } from "@/sales/invoices/InvoiceScreen";

interface Params {
  org: string;
}

/** New invoice, `/o/:org/sales/invoices/new` — where quick-create N I lands (D-03a-T13, T17). */
export default async function NewInvoicePage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org}>
      <InvoiceScreen org={org} />
    </AppShell>
  );
}
