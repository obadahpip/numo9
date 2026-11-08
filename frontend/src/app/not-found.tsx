import Link from "next/link";

import { NotFoundSearch } from "@/components/NotFoundSearch";
import { defineMessages, formatMessage } from "@/i18n";

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

/** Custom 404 (S-01-T14, gap #2): explains, offers search over known pages and a way Home. */
export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">{formatMessage(messages.title)}</h1>
        <p className="mt-2 text-sm text-gray-600">{formatMessage(messages.body)}</p>
      </div>
      <NotFoundSearch />
      <Link
        href="/"
        className="self-start rounded border border-[var(--color-border)] px-4 py-2 text-sm font-medium"
      >
        {formatMessage(messages.home)}
      </Link>
    </main>
  );
}
