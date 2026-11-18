import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ContactForm } from "@/contacts/ContactForm";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
  id: string;
}

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** A contact (B-01-T15), `/o/:org/contacts/:id`. */
export default async function ContactPage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !ID.test(id)) notFound();
  return (
    <AppShell org={org} modulePath="contacts">
      <ContactForm org={org} id={id} />
    </AppShell>
  );
}
