import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ContactForm } from "@/contacts/ContactForm";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** New contact (B-01-T15), `/o/:org/contacts/new`. */
export default async function NewContactPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="contacts">
      <ContactForm org={org} />
    </AppShell>
  );
}
