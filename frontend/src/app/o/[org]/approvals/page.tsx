import { notFound } from "next/navigation";

import { ApprovalsInbox } from "@/approvals/ApprovalsInbox";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Approvals inbox (C-04-T12), `/o/:org/approvals`. */
export default async function ApprovalsPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="accounting/journals">
      <ApprovalsInbox org={org} />
    </AppShell>
  );
}
