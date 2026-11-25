import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ReportsHome } from "@/reports/ReportsHome";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Reports (K-01-T12), `/o/:org/reports`: search, categories, favourites, saved layouts. */
export default async function ReportsPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="reports">
      <ReportsHome org={org} />
    </AppShell>
  );
}
