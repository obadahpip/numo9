"use client";

/**
 * PO match panel (E-02-T13): per bill line from a purchase order — ordered, received, billed
 * before, this bill's quantity and price against the PO's — and a coloured result: green
 * (matches), amber (within the receipt tolerance), red (doesn't match: more than received or a
 * price beyond the tolerance). Colour is never alone: each result is also in words.
 */
import { formatMoney, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";

import { useFormatMessage } from "@/i18n";

import type { MatchRow } from "./api";
import { match as m } from "./messages";

const TONES = {
  green: "bg-surface-success-subtle text-fg",
  amber: "bg-surface-warning-subtle text-fg",
  red: "bg-surface-danger-subtle text-fg-danger",
} as const;

const qty = (value: string) => String(Number(value));

export function MatchPanel({ rows }: { rows: MatchRow[] }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  if (!rows.length) return null;
  const po = rows[0]?.po ?? "";
  return (
    <section aria-labelledby="bill-match" className="flex flex-col gap-2" data-match-panel="">
      <h2 id="bill-match" className="text-sm font-semibold text-fg">
        {fm(m.title, { po })}
      </h2>
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <thead className="bg-surface-muted text-xs text-fg-muted">
            <tr>
              <th scope="col" className="px-2 py-1.5 text-start font-semibold">
                {fm(m.line)}
              </th>
              <th scope="col" className="px-2 py-1.5 text-end font-semibold">
                {fm(m.ordered)}
              </th>
              <th scope="col" className="px-2 py-1.5 text-end font-semibold">
                {fm(m.received)}
              </th>
              <th scope="col" className="px-2 py-1.5 text-end font-semibold">
                {fm(m.billedElsewhere)}
              </th>
              <th scope="col" className="px-2 py-1.5 text-end font-semibold">
                {fm(m.quantity)}
              </th>
              <th scope="col" className="px-2 py-1.5 text-end font-semibold">
                {fm(m.price)}
              </th>
              <th scope="col" className="px-2 py-1.5 text-start font-semibold">
                {fm(m.result)}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const details = [
                Number(row.quantity_over) > 0
                  ? fm(m.over, { quantity: qty(row.quantity_over) })
                  : "",
                Number(row.price_difference_pct) > 0
                  ? fm(m.priceDiff, { pct: String(Number(row.price_difference_pct)) })
                  : "",
              ].filter(Boolean);
              return (
                <tr key={row.line} className="border-t border-border" data-match={row.status}>
                  <th scope="row" className="px-2 py-1.5 text-start font-normal">
                    {row.description}
                  </th>
                  <td className="px-2 py-1.5 text-end tabular-nums">{qty(row.ordered)}</td>
                  <td className="px-2 py-1.5 text-end tabular-nums">{qty(row.received)}</td>
                  <td className="px-2 py-1.5 text-end tabular-nums">{qty(row.billed_elsewhere)}</td>
                  <td className="px-2 py-1.5 text-end tabular-nums">{qty(row.quantity)}</td>
                  <td className="px-2 py-1.5 text-end tabular-nums">
                    {fm(m.priceCell, {
                      price: formatMoney(row.price, { locale }),
                      po: formatMoney(row.po_price, { locale }),
                    })}
                  </td>
                  <td className="px-2 py-1.5">
                    <span
                      className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${TONES[row.status]}`}
                    >
                      {fm(m[row.status])}
                    </span>
                    {details.length ? (
                      <span className="block text-xs text-fg-muted">{details.join(" · ")}</span>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
