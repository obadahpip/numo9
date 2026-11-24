import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { RecurringJournals } from "@/journals/recurring/RecurringJournals";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Accounting → Journals → Recurring (C-04-T11), `/o/:org/accounting/journals/recurring?id=`. */
export default async function RecurringJournalsPage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<{ id?: string }>;
}) {
  const { org } = await params;
  const { id } = await searchParams;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="accounting/journals">
      <RecurringJournals org={org} initial={id && UUID.test(id) ? id : undefined} />
    </AppShell>
  );
}
