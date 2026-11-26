import { notFound } from "next/navigation";

import { AssuranceScreen } from "@/accounting/assurance/AssuranceScreen";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Accounting → assurance: score, grouped findings and their fixes (K-09-T21). */
export default async function AssurancePage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="accounting/journals">
      <AssuranceScreen org={org} />
    </AppShell>
  );
}
