import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { RecurringInvoiceList } from "@/sales/recurring/RecurringInvoiceList";

interface Params {
  org: string;
}

/** Sales → Recurring invoices (D-04-T10), `/o/:org/sales/recurring-invoices`. */
export default async function RecurringInvoicesPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org}>
      <RecurringInvoiceList org={org} />
    </AppShell>
  );
}
