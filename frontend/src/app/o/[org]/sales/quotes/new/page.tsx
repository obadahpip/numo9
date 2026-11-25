import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";
import { ORG_SLUG } from "@/routing/routes";

const messages = defineMessages({
  title: { id: "sales.newQuote.title", defaultMessage: "New quote", description: "Heading" },
  placeholder: {
    id: "sales.newQuote.placeholder",
    defaultMessage: "The quote editor arrives with the next release of Sales.",
    description: "Body text until the quote editor is built",
  },
});

interface Params {
  org: string;
}

/**
 * New quote, `/o/:org/sales/quotes/new` — where quick-create N Q lands (D-02-T16). The quote
 * editor (D-02-T12) replaces this placeholder.
 */
export default async function NewQuotePage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  const fm = await getFormatMessage();
  return (
    <AppShell org={org}>
      <h1 className="text-xl font-semibold text-fg">{fm(messages.title)}</h1>
      <p className="mt-2 text-sm text-fg-muted">{fm(messages.placeholder)}</p>
    </AppShell>
  );
}
