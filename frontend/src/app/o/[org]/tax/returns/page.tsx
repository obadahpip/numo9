import { notFound } from "next/navigation";

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
      <ReturnsScreen org={org} />
    </AppShell>
  );
}
