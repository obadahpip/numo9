import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";
import { ORG_SLUG } from "@/routing/routes";

const messages = defineMessages({
  title: { id: "sales.newInvoice.title", defaultMessage: "New invoice", description: "Heading" },
  placeholder: {
    id: "sales.newInvoice.placeholder",
    defaultMessage: "The invoice editor arrives with the next release of Sales.",
    description: "Body text until the invoice editor is built",
  },
});

interface Params {
  org: string;
}

/**
 * New invoice, `/o/:org/sales/invoices/new` — where quick-create N I lands (D-03a-T17). The invoice
 * editor (D-03a-T13) replaces this placeholder.
 */
export default async function NewInvoicePage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  const fm = await getFormatMessage();
  return (
    <AppShell org={org}>
      <h1 className="text-xl font-semibold text-fg">{fm(messages.title)}</h1>
      <p className="mt-2 text-sm text-fg-muted">{fm(messages.placeholder)}</p>
    </AppShell>
  );
}
