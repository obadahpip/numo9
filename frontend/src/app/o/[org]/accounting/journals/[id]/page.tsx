import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { JournalViewer } from "@/journals/JournalViewer";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
  id: string;
}

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Accounting → Journals → one journal (C-02-T16), `/o/:org/accounting/journals/:id`. */
export default async function JournalPage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !ID.test(id)) notFound();
  return (
    <AppShell org={org} modulePath="accounting/journals">
      <JournalViewer org={org} id={id} />
    </AppShell>
  );
}
