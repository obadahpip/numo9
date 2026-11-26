import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { RecurringInvoiceScreen } from "@/sales/recurring/RecurringInvoiceScreen";

interface Params {
  org: string;
  id: string;
}

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Sales → one recurring invoice (D-04-T08), `/o/:org/sales/recurring-invoices/:id`. */
export default async function RecurringInvoicePage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !ID.test(id)) notFound();
  return (
    <AppShell org={org}>
      <RecurringInvoiceScreen org={org} id={id} />
    </AppShell>
  );
}
