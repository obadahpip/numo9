"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId, useState } from "react";

import { defineMessages, formatMessage } from "@/i18n";
import { editDistance } from "@/routing/redirects";
import { ORG_MODULES } from "@/routing/routes";

const messages = defineMessages({
  label: {
    id: "notFound.search.label",
    defaultMessage: "Search pages",
    description: "Label of the search box on the 404 page",
  },
  results: {
    id: "notFound.search.results",
    defaultMessage: "Matching pages",
    description: "Accessible name of the 404 search result list",
  },
  noResults: {
    id: "notFound.search.noResults",
    defaultMessage: "No matching pages. Try another word.",
    description: "Shown when the 404 search finds nothing",
  },
});

interface Destination {
  label: string;
  /** Short, organisation-independent URL; the redirect map sends it to the current organisation. */
  href: string;
  /** Lowercase words from the label, the module path and its aliases. */
  terms: readonly string[];
}

const DESTINATIONS: readonly Destination[] = ORG_MODULES.map((module) => ({
  label: formatMessage(module.label),
  href: `/${module.path}`,
  terms: [
    ...new Set(
      [formatMessage(module.label), module.path, ...module.aliases]
        .join(" ")
        .toLowerCase()
        .split(/[^a-z0-9]+/)
        .filter((term) => term.length >= 2),
    ),
  ],
}));

function matches(word: string, term: string): boolean {
  if (word.length < 2) return false;
  if (term.startsWith(word) || (word.length >= 4 && term.includes(word))) return true;
  if (word.length < 4) return false;
  return editDistance(word, term) <= (word.length >= 8 ? 2 : 1);
}

/** Words worth searching for from a broken URL, e.g. "/o/acme/chart-acounts" → "chart acounts". */
export function queryFromPath(pathname: string): string {
  const segments = pathname
    .split("/")
    .filter((segment) => segment !== "" && segment.toLowerCase() !== "o");
  const last = segments.at(-1) ?? "";
  return decodeURIComponent(last)
    .replace(/\.(aspx|html?)$/i, "")
    .replace(/[-_.]+/g, " ")
    .trim()
    .toLowerCase();
}

export function searchDestinations(query: string): Destination[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return [...DESTINATIONS];
  return DESTINATIONS.filter((destination) =>
    words.some((word) => destination.terms.some((term) => matches(word, term))),
  );
}

export function NotFoundSearch() {
  const pathname = usePathname() ?? "";
  const [query, setQuery] = useState(() => queryFromPath(pathname));
  const inputId = useId();
  const results = searchDestinations(query);

  return (
    <section className="flex flex-col gap-3" role="search">
      <label htmlFor={inputId} className="text-sm font-medium">
        {formatMessage(messages.label)}
      </label>
      <input
        id={inputId}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        className="rounded border border-[var(--color-border)] px-3 py-2"
        autoComplete="off"
      />
      {results.length > 0 ? (
        <ul aria-label={formatMessage(messages.results)} className="flex flex-col gap-1">
          {results.map((destination) => (
            <li key={destination.href}>
              <Link href={destination.href} className="text-sm underline">
                {destination.label}
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-gray-600">{formatMessage(messages.noResults)}</p>
      )}
    </section>
  );
}
