import { notFound } from "next/navigation";

import { ConversionScreen } from "@/accounting/conversion/ConversionScreen";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Accounting → conversion balances (C-05-T10…T12), `/o/:org/accounting/conversion`. */
export default async function ConversionPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="accounting/conversion">
      <ConversionScreen org={org} />
    </AppShell>
  );
}
