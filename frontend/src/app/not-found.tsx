import { BUTTON_BASE, ExplainPanel } from "@numo9/ui";
import Link from "next/link";

import { NotFoundSearch } from "@/components/NotFoundSearch";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";

const messages = defineMessages({
  title: {
    id: "notFound.title",
    defaultMessage: "We can't find that page",
    description: "Heading of the 404 page",
  },
  body: {
    id: "notFound.body",
    defaultMessage:
      "The address may be mistyped, or the page may have moved. Search for the page or go to Home.",
    description: "Explanation on the 404 page",
  },
  home: { id: "notFound.home", defaultMessage: "Go to Home", description: "Link back to Home" },
});

/**
 * Custom 404 (S-01-T14, gap #2): explains, offers search over known pages and a way Home. Built
 * on the design system's ExplainPanel (A-10-T12) like every other "not available" screen.
 */
export default async function NotFound() {
  const fm = await getFormatMessage();
  return (
    <main className="flex min-h-screen flex-col justify-center p-6">
      <ExplainPanel
        kind="notFound"
        headingLevel={1}
        title={fm(messages.title)}
        body={fm(messages.body)}
        actions={[
          <Link
            key="home"
            href="/"
            className={`${BUTTON_BASE} min-h-touch-target border border-border-strong px-4 text-sm`}
          >
            {fm(messages.home)}
          </Link>,
        ]}
      >
        <NotFoundSearch />
      </ExplainPanel>
    </main>
  );
}
