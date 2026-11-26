import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { RecurringInvoiceScreen } from "@/sales/recurring/RecurringInvoiceScreen";

interface Params {
  org: string;
}

/** New recurring invoice, `/o/:org/sales/recurring-invoices/new` (D-04-T08). */
export default async function NewRecurringInvoicePage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org}>
      <RecurringInvoiceScreen org={org} />
    </AppShell>
  );
}
