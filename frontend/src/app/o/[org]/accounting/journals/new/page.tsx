import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { JournalForm } from "@/journals/write/JournalForm";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Accounting → Journals → new manual journal (C-03-T11), `/o/:org/accounting/journals/new`. */
export default async function NewJournalPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="accounting/journals">
      <JournalForm org={org} />
    </AppShell>
  );
}
