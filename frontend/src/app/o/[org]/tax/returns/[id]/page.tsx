import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";
import { ReturnWorksheet } from "@/tax/returns/ReturnWorksheet";

interface Params {
  org: string;
  id: string;
}

const UUID = /^[0-9a-f-]{1,64}$/i;

/** Tax → a GST/HST return worksheet (G-03-T11, T12). */
export default async function ReturnPage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !UUID.test(id)) notFound();
  return (
    <AppShell org={org} modulePath="reports">
      <ReturnWorksheet org={org} id={id} />
    </AppShell>
  );
}
