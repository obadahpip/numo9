"use client";

/**
 * The console's catalogue section (U-06-T07): the U-02 package editor, the U-01 product list and
 * the U-02 promo codes are reused as they are, under one console area ("Packages and prices") with
 * this sub-navigation between them, inside the console frame (guard, console nav).
 */
import Link from "next/link";

import { defineMessages, useFormatMessage } from "@/i18n";

const messages = defineMessages({
  nav: {
    id: "console.catalogue.nav",
    defaultMessage: "Catalogue",
    description: "Accessible name of the console's catalogue sub-navigation",
  },
  packages: { id: "console.catalogue.packages", defaultMessage: "Packages", description: "Tab" },
  products: { id: "console.catalogue.products", defaultMessage: "Products", description: "Tab" },
  promoCodes: {
    id: "console.catalogue.promoCodes",
    defaultMessage: "Promo codes",
    description: "Tab",
  },
});

export const CATALOGUE_TABS = [
  { href: "/console/packages", label: messages.packages },
  { href: "/console/products", label: messages.products },
  { href: "/console/promo-codes", label: messages.promoCodes },
] as const;

export type CatalogueTab = (typeof CATALOGUE_TABS)[number]["href"];

export function CatalogueNav({ current }: { current: CatalogueTab }) {
  const fm = useFormatMessage();
  return (
    <nav aria-label={fm(messages.nav)} className="flex gap-1 border-b border-border">
      {CATALOGUE_TABS.map((tab) => {
        const active = tab.href === current;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={active ? "page" : undefined}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-semibold ${
              active ? "border-border-accent text-fg" : "border-transparent text-fg-muted"
            }`}
          >
            {fm(tab.label)}
          </Link>
        );
      })}
    </nav>
  );
}
