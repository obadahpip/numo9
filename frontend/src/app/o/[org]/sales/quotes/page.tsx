import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { QuotesList } from "@/sales/quotes/QuotesList";

interface Params {
  org: string;
}

/** Sales → Quotes (D-02-T14), `/o/:org/sales/quotes`: the list tabs with their counts. */
export default async function QuotesPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org}>
      <QuotesList org={org} />
    </AppShell>
  );
}
