import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ContactsScreen } from "@/contacts/ContactsScreen";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Contacts (B-01-T14), `/o/:org/contacts`. */
export default async function ContactsPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="contacts">
      <ContactsScreen org={org} />
    </AppShell>
  );
}
