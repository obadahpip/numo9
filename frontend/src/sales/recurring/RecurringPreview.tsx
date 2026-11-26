"use client";

/**
 * "Preview next invoice" (D-04-T09): the next invoice of a saved template — or the one of any
 * of its next dates — exactly as the generator will make it: the server builds it with the
 * generator's own code and throws it away, so the placeholders are resolved in the customer's
 * language, the due date and a prorated partial period are those of the real invoice, and a date
 * that would be skipped (a lock date, an archived customer) says why.
 */
import { Badge, Skeleton, formatDate, formatMoney, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { recurringInvoicesApi, type RecurringPreview as Preview } from "./api";
import { rim } from "./messages";

export function RecurringPreview({
  org,
  id,
  refresh = 0,
}: Readonly<{ org: string; id: string; refresh?: number }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [date, setDate] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let current = true;
    setFailed(false);
    void recurringInvoicesApi
      .preview(org, id, date || undefined)
      .then((r) => {
        if (!current) return;
        if (r.status === 200) setPreview(r.body);
        else setFailed(true);
      })
      .catch(() => current && setFailed(true));
    return () => {
      current = false;
    };
  }, [org, id, date, refresh]);

  const money = (amount: string) => formatMoney(amount, { locale });
  const invoice = preview?.invoice ?? null;

  return (
    <section
      aria-labelledby={`${ids}-title`}
      className="flex flex-col gap-3 rounded-md border border-border p-4"
      data-recurring-preview=""
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id={`${ids}-title`} className="text-base font-semibold text-fg">
          {fm(rim.previewTitle)}
        </h2>
        {preview && preview.dates.length ? (
          <label className="flex items-center gap-2 text-sm text-fg">
            {fm(rim.previewDate)}
            <select
              value={date || invoice?.date || ""}
              onChange={(e) => setDate(e.target.value)}
              className="min-h-touch-target rounded-md border border-border bg-surface px-2 text-sm text-fg"
            >
              {preview.dates.map((day) => (
                <option key={day} value={day}>
                  {formatDate(day, { locale })}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>
      {failed ? (
        <p role="alert" className="text-sm text-fg-danger">
          {fm(rim.previewFailed)}
        </p>
      ) : preview === null ? (
        <Skeleton className="h-40" />
      ) : invoice === null ? (
        <p className="text-sm text-fg-muted">{fm(rim.previewNone)}</p>
      ) : (
        <>
          {invoice.skip ? (
            <p role="alert" className="text-sm text-fg-warning" data-preview-skip="">
              {fm(rim.previewSkipped, { reason: invoice.skip.message })}
            </p>
          ) : null}
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
            <dt className="text-fg-muted">{fm(rim.previewCustomer)}</dt>
            <dd>{invoice.customer.name}</dd>
            <dt className="text-fg-muted">{fm(rim.previewInvoiceDate)}</dt>
            <dd data-preview-date="">{formatDate(invoice.date, { locale })}</dd>
            <dt className="text-fg-muted">{fm(rim.previewDue)}</dt>
            <dd>{invoice.due_date ? formatDate(invoice.due_date, { locale }) : ""}</dd>
            <dt className="text-fg-muted">{fm(rim.reference)}</dt>
            <dd data-preview-reference="">{invoice.reference}</dd>
            <dt className="text-fg-muted">{fm(rim.previewPeriod)}</dt>
            <dd>
              {fm(rim.previewPeriodValue, {
                start: formatDate(invoice.period.start, { locale }),
                end: formatDate(invoice.period.end, { locale }),
              })}
            </dd>
          </dl>
          {invoice.proration.full ? null : (
            <Badge tone="info">
              {fm(rim.previewProrated, {
                covered: invoice.proration.covered,
                days: invoice.proration.days,
              })}
            </Badge>
          )}
          <table className="w-full text-sm" data-preview-lines="">
            <caption className="sr-only">{fm(rim.previewLines)}</caption>
            <thead>
              <tr className="text-xs text-fg-muted">
                <th scope="col" className="py-1 text-start">
                  {fm(rim.previewDescription)}
                </th>
                <th scope="col" className="py-1 text-end">
                  {fm(rim.previewQuantity)}
                </th>
                <th scope="col" className="py-1 text-end">
                  {fm(rim.previewAmount)}
                </th>
              </tr>
            </thead>
            <tbody>
              {invoice.lines.map((line) => (
                <tr key={line.position} className="border-t border-border">
                  <td className="py-1">{line.description}</td>
                  <td className="py-1 text-end tabular-nums">{Number(line.quantity)}</td>
                  <td className="py-1 text-end tabular-nums">{money(line.net)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm tabular-nums">
            <dt className="text-fg-muted">{fm(rim.previewSubtotal)}</dt>
            <dd className="text-end">{money(invoice.subtotal)}</dd>
            <dt className="text-fg-muted">{fm(rim.previewTax)}</dt>
            <dd className="text-end">{money(invoice.tax_total)}</dd>
            <dt className="font-semibold text-fg">{fm(rim.previewTotal)}</dt>
            <dd className="text-end font-semibold" data-preview-total="">
              {money(invoice.total)}
            </dd>
          </dl>
          {invoice.notes ? (
            <p className="whitespace-pre-line text-sm text-fg" data-preview-notes="">
              {invoice.notes}
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
