import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ImportWizard } from "@/imports/ImportWizard";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Contacts import wizard (B-03-T12), `/o/:org/contacts/import`. */
export default async function ContactsImportPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="contacts">
      <ImportWizard org={org} />
    </AppShell>
  );
}
