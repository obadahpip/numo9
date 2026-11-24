import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { JournalForm } from "@/journals/write/JournalForm";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Accounting → Journals → new manual journal (C-03-T11), `/o/:org/accounting/journals/new`;
 * `?copy=<journal>` starts from another journal's lines (Copy journal, C-04-T10). */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default async function NewJournalPage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<{ copy?: string }>;
}) {
  const { org } = await params;
  const { copy } = await searchParams;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="accounting/journals">
      <JournalForm org={org} copyOf={copy && UUID.test(copy) ? copy : null} />
    </AppShell>
  );
}
