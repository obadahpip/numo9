import { notFound } from "next/navigation";

import { RecodeScreen } from "@/accounting/recode/RecodeScreen";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Accounting → find and recode with undo (C-07-T10 – T13). */
export default async function RecodePage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="accounting/journals">
      <RecodeScreen org={org} />
    </AppShell>
  );
}
