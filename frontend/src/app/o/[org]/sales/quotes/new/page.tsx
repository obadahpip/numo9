import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { QuoteScreen } from "@/sales/quotes/QuoteScreen";

interface Params {
  org: string;
}

/** New quote, `/o/:org/sales/quotes/new` — where quick-create N Q lands (D-02-T12, T16). */
export default async function NewQuotePage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org}>
      <QuoteScreen org={org} />
    </AppShell>
  );
}
