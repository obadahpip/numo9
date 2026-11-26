import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { CommitmentReport } from "@/purchases/orders/CommitmentReport";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Purchases → commitments (E-01-T14), `/o/:org/purchases/commitments`: open PO value. */
export default async function CommitmentsPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="purchases/orders">
      <CommitmentReport org={org} />
    </AppShell>
  );
}
