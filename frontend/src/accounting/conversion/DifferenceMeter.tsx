"use client";

/**
 * Difference meter (C-05-T11): a bar **sticky at the bottom** of the conversion wizard —
 * "Debits 120,450.00 · Credits 120,437.50 · Difference 12.50 — Finalise unavailable" — recomputed
 * in the browser on every keystroke (`meterTotals`), and the Finalise button: **disabled while
 * anything blocks it**, with a tooltip naming the difference (and every other reason: AR/AP not
 * equal to the open documents, an account without its contact…). The reasons are also listed as
 * text under the figures (a tooltip is never the only place information lives). Finalise asks
 * for confirmation first — saying what is posted and, when chosen, what gets locked.
 */
import { Button, Dialog, formatDate, formatMoney, Tooltip, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useId, useMemo, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { conversionApi, type Difference, type Overview } from "./api";
import { blockers, meterTotals, type Blocker, type MeterRow } from "./meter";
import { mm } from "./meterMessages";

export interface DifferenceMeterProps {
  org: string;
  rows: readonly MeterRow[];
  server: Difference | null;
  conversionDate: string;
  finalised: boolean;
  lockBalances: boolean;
  onFinalised: (overview: Overview) => void;
}

function dayBefore(iso: string): string {
  const day = new Date(`${iso}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() - 1);
  return day.toISOString().slice(0, 10);
}

export function DifferenceMeter({
  org,
  rows,
  server,
  conversionDate,
  finalised,
  lockBalances,
  onFinalised,
}: DifferenceMeterProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const totals = useMemo(() => meterTotals(rows, locale), [rows, locale]);
  const blocked = blockers(totals, server, finalised);
  const money = (value: string) => formatMoney(value, { locale, currency: "CAD" });
  const plain = (value: string) =>
    money(value)
      .replace(/[^\d.,\s  -]/g, "")
      .trim();
  const reason = (blocker: Blocker): string => {
    switch (blocker.kind) {
      case "finalised":
        return fm(mm.finalised);
      case "empty":
        return fm(mm.empty);
      case "unreadable":
        return fm(mm.unreadable, { count: blocker.count });
      case "unbalanced":
        return fm(mm.unbalanced, { difference: plain(blocker.difference) });
      case "server":
        return blocker.reason.message;
    }
  };
  const reasons = blocked.map(reason);
  const figures = fm(mm.totals, {
    debits: plain(totals.debits),
    credits: plain(totals.credits),
    difference: plain(totals.difference.replace("-", "")),
  });

  const finalise = async () => {
    setBusy(true);
    setError("");
    const answer = await conversionApi.finalise(org, lockBalances).catch(() => null);
    setBusy(false);
    if (answer?.status === 200) {
      setOpen(false);
      onFinalised(answer.body);
      return;
    }
    setError(answer?.body.detail || fm(mm.failed));
  };

  const button = (
    <Button
      variant="primary"
      disabled={blocked.length > 0 || busy}
      aria-describedby={blocked.length ? `${ids}-why` : undefined}
      onClick={() => setOpen(true)}
      data-finalise=""
    >
      {busy ? fm(mm.finalising) : fm(mm.finalise)}
    </Button>
  );

  return (
    <section
      aria-label={fm(mm.region)}
      data-meter=""
      data-balanced={totals.balanced || undefined}
      className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface px-4 py-3 shadow-elevation-2"
    >
      <div className="flex flex-col gap-1">
        <p className="text-sm font-semibold text-fg tabular-nums" data-figures="">
          <span>{figures}</span>
          <span className={blocked.length ? "ms-1 text-fg-danger" : "ms-1 text-fg-success"}>
            {blocked.length ? fm(mm.unavailable) : fm(mm.ready)}
          </span>
        </p>
        {blocked.length ? (
          <ul id={`${ids}-why`} aria-label={fm(mm.why)} className="text-xs text-fg-muted">
            {reasons.map((text) => (
              <li key={text} data-reason="">
                {text}
              </li>
            ))}
          </ul>
        ) : null}
        {error ? (
          <p role="alert" className="text-xs text-fg-danger">
            {error}
          </p>
        ) : null}
      </div>
      {blocked.length ? (
        <Tooltip content={reasons.join(" ")}>
          {/* A disabled button gets no hover or focus: the wrapper carries the tooltip. */}
          <span tabIndex={0} data-finalise-reason={reasons.join(" ")} className="inline-flex">
            {button}
          </span>
        </Tooltip>
      ) : (
        button
      )}
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={fm(mm.confirmTitle)}
        closeLabel={fm(mm.cancel)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              {fm(mm.cancel)}
            </Button>
            <Button variant="primary" disabled={busy} onClick={finalise}>
              {fm(mm.confirm)}
            </Button>
          </>
        }
      >
        <p className="text-sm text-fg">
          {fm(mm.confirmBody, { date: formatDate(conversionDate, { locale }) })}
        </p>
        {lockBalances ? (
          <p className="mt-2 text-sm text-fg">
            {fm(mm.confirmLock, { date: formatDate(dayBefore(conversionDate), { locale }) })}
          </p>
        ) : null}
      </Dialog>
    </section>
  );
}
