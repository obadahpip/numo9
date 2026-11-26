import { notFound } from "next/navigation";

import { Gated } from "@/catalogue/Gated";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { ReturnsScreen } from "@/tax/returns/ReturnsScreen";

interface Params {
  org: string;
}

/** Tax → GST/HST returns (G-03-T11). */
export default async function ReturnsPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="reports">
      {/* Part of every package with Tax (G-03-T15, gap-54); elsewhere the locked panel. */}
      <Gated feature="tax.returns.read" headingLevel={1}>
        <ReturnsScreen org={org} />
      </Gated>
    </AppShell>
  );
}
