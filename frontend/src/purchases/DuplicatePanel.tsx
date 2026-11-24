"use client";

/**
 * Duplicate warning panel (E-02-T12): the look-alikes of the bill (E-02-T03 — same supplier,
 * amount within 1 %, date within 10 days) beside the form after each save. A warning only: the
 * bill can still be approved.
 */
import { formatDate, formatMoney, type AppLocale } from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";

import { useFormatMessage } from "@/i18n";

import type { DuplicateSuspect } from "./api";
import { checks } from "./messages";

export function DuplicatePanel({ org, suspects }: { org: string; suspects: DuplicateSuspect[] }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  if (!suspects.length) return null;
  return (
    <section
      aria-labelledby="bill-duplicates"
      className="rounded-md border border-border bg-surface-warning-subtle p-3 text-sm"
      data-duplicates=""
    >
      <h2 id="bill-duplicates" className="font-semibold text-fg">
        {fm(checks.duplicatesTitle)}
      </h2>
      <p className="text-fg-muted">{fm(checks.duplicatesBody)}</p>
      <ul className="mt-2 flex flex-col gap-1">
        {suspects.map((suspect) => {
          const name = suspect.number || suspect.supplier_invoice_no || fm(checks.draftBill);
          return (
            <li key={suspect.id} className="flex flex-wrap items-center gap-2 text-fg">
              <span>
                {fm(checks.suspectLine, {
                  date: formatDate(suspect.date, { locale, timeZone: "America/Toronto" }),
                  total: formatMoney(suspect.total, { locale }),
                })}
              </span>
              <Link href={`/o/${org}/purchases/bills/${suspect.id}`} className="underline">
                {fm(checks.openSuspect, { bill: name })}
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
