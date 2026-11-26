"use client";

/**
 * The period ribbon (D-03a-T14): above the invoice, what its date falls in — an open period, or
 * on or before the sales (AR) lock date; and its GST/HST filing period, marked when filed (then
 * approving is refused with the period named, D-03a-T04). Read from the invoice's preview; a new
 * invoice shows it once saved.
 */
import { LockIcon, cn, formatDate, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { invoicesApi, type PeriodRibbon as Ribbon } from "./api";
import { im } from "./messages";

export function PeriodRibbon({
  org,
  id,
  refresh = 0,
}: {
  org: string;
  id: string | null;
  refresh?: number;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [ribbon, setRibbon] = useState<Ribbon | null>(null);

  useEffect(() => {
    if (!id) return setRibbon(null);
    let live = true;
    void invoicesApi.preview(org, id).then((answer) => {
      if (live && answer.status === 200) setRibbon(answer.body.period);
    });
    return () => {
      live = false;
    };
  }, [org, id, refresh]);

  if (!ribbon) return null;
  const day = (value: string) => formatDate(value, { locale });
  const tax = ribbon.tax_period;
  const blocked = ribbon.locked || Boolean(tax?.filed);
  return (
    <div
      role="group"
      aria-label={fm(im.ribbon)}
      data-period-ribbon={blocked ? "blocked" : "open"}
      className={cn(
        "flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border px-3 py-2 text-sm",
        blocked ? "border-border-danger bg-surface-danger" : "border-border bg-surface-subtle",
      )}
    >
      <span className="inline-flex items-center gap-1 font-medium">
        {ribbon.locked ? (
          <>
            <LockIcon />
            {fm(im.ribbonLocked, { date: day(ribbon.lock?.date ?? ribbon.ar_lock ?? "") })}
          </>
        ) : (
          fm(im.ribbonOpen)
        )}
      </span>
      {ribbon.ar_lock && !ribbon.locked ? (
        <span className="text-fg-muted">{fm(im.ribbonLock, { date: day(ribbon.ar_lock) })}</span>
      ) : null}
      {tax ? (
        <span
          className={cn(
            "inline-flex items-center gap-1",
            tax.filed ? "font-medium" : "text-fg-muted",
          )}
          data-tax-period={tax.filed ? "filed" : "open"}
        >
          {tax.filed ? <LockIcon /> : null}
          {fm(tax.filed ? im.ribbonTaxFiled : im.ribbonTax, {
            start: day(tax.start),
            end: day(tax.end),
          })}
        </span>
      ) : null}
    </div>
  );
}
