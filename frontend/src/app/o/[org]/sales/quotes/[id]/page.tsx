import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { QuoteScreen } from "@/sales/quotes/QuoteScreen";

interface Params {
  org: string;
  id: string;
}

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Sales → one quote (D-02-T12), `/o/:org/sales/quotes/:id`. */
export default async function QuotePage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !ID.test(id)) notFound();
  return (
    <AppShell org={org}>
      <QuoteScreen org={org} id={id} />
    </AppShell>
  );
}
