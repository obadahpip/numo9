import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { DocumentsInbox } from "@/files/DocumentsInbox";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/**
 * Documents inbox (A-06-T12), `/o/:org/documents`. Replaces the route-registry placeholder.
 */
export default async function DocumentsPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="documents">
      <DocumentsInbox org={org} />
    </AppShell>
  );
}
