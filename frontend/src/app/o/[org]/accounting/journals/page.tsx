import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { isJournalTab } from "@/journals/api";
import { JournalsList } from "@/journals/JournalsList";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Accounting → Journals (K-09-T22), `/o/:org/accounting/journals?tab=draft` — the status tabs. */
export default async function JournalsPage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const { org } = await params;
  const { tab } = await searchParams;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="accounting/journals">
      <JournalsList org={org} initialTab={isJournalTab(tab) ? tab : "all"} />
    </AppShell>
  );
}
