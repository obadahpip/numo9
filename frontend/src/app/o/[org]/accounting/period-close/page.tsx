import { notFound } from "next/navigation";

import { PeriodCloseScreen } from "@/accounting/period-close/PeriodCloseScreen";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Accounting → period close and year-end (C-06-T08, T09). */
export default async function PeriodClosePage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="accounting/journals">
      <PeriodCloseScreen org={org} />
    </AppShell>
  );
}
