"use client";

/**
 * Recurring invoices list (D-04-T10), `/o/:org/sales/recurring-invoices`: the templates with
 * their schedule, mode, **next run**, **last run**, **status** (active / paused / ended — the tabs,
 * with the server's counts) and how many invoices each generated and dates it skipped; search by
 * name, reference or customer.
 */
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Input,
  Skeleton,
  formatDate,
  formatMoney,
  type AppLocale,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useId, useState } from "react";

import { useDebounced } from "@/directory/useDebounced";
import { useFormatMessage } from "@/i18n";
import { readRule } from "@/journals/recurring/api";

import {
  recurringInvoicesApi,
  recurringUrl,
  type Page,
  type RecurringRow,
  type RecurringRun,
  type RecurringStatus,
} from "./api";
import { rim } from "./messages";

const TABS: readonly (RecurringStatus | "all")[] = ["all", "active", "paused", "ended"];
export const SEARCH_DEBOUNCE_MS = 300;
/** An empty cell (no date, no invoice). */
const NONE = "—";

export function RecurringInvoiceList({ org }: Readonly<{ org: string }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [tab, setTab] = useState<RecurringStatus | "all">("all");
  const [text, setText] = useState("");
  const q = useDebounced(text.trim(), SEARCH_DEBOUNCE_MS);
  const [page, setPage] = useState<Page<RecurringRow, RecurringStatus> | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    const query: Record<string, string> = {};
    if (tab !== "all") query.status = tab;
    if (q) query.q = q;
    setFailed(false);
    return recurringInvoicesApi
      .list(org, query)
      .then((r) => (r.status === 200 ? setPage(r.body) : setFailed(true)))
      .catch(() => setFailed(true));
  }, [org, tab, q]);
  useEffect(() => {
    void load();
  }, [load]);

  const day = (value: string | null) => (value ? formatDate(value, { locale }) : NONE);
  const total = (counts: Record<RecurringStatus, number>) =>
    counts.active + counts.paused + counts.ended;

  return (
    <div className="flex flex-col gap-5" data-recurring-invoice-list="">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 id={`${ids}-title`} className="text-2xl font-semibold text-fg">
          {fm(rim.listTitle)}
        </h1>
        <Link
          href={`${recurringUrl(org)}/new`}
          className="rounded-md border border-border px-3 py-2 text-sm font-semibold text-fg"
        >
          {fm(rim.add)}
        </Link>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" aria-label={fm(rim.tabs)} className="flex flex-wrap gap-1">
          {TABS.map((name) => (
            <button
              key={name}
              type="button"
              role="tab"
              aria-selected={tab === name}
              onClick={() => setTab(name)}
              className={`rounded-md px-3 py-1.5 text-sm ${
                tab === name ? "bg-surface-muted font-semibold text-fg" : "text-fg-muted"
              }`}
            >
              {fm(rim.tab, {
                status: name,
                count: page ? (name === "all" ? total(page.counts) : page.counts[name]) : 0,
              })}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-fg">
          <span className="sr-only">{fm(rim.search)}</span>
          <Input
            type="search"
            value={text}
            placeholder={fm(rim.search)}
            onChange={(e) => setText(e.target.value)}
          />
        </label>
      </div>
      {failed ? (
        <ErrorState
          title={fm(rim.listFailed)}
          retryLabel={fm(rim.retry)}
          onRetry={() => void load()}
        />
      ) : page === null ? (
        <Skeleton className="h-48" />
      ) : page.results.length === 0 ? (
        <EmptyState title={fm(rim.emptyTitle)} body={fm(rim.emptyBody)} />
      ) : (
        <table className="w-full text-sm" aria-labelledby={`${ids}-title`}>
          <thead>
            <tr className="text-xs text-fg-muted">
              <th scope="col" className="py-1 text-start">
                {fm(rim.name)}
              </th>
              <th scope="col" className="py-1 text-start">
                {fm(rim.customer)}
              </th>
              <th scope="col" className="py-1 text-start">
                {fm(rim.schedule)}
              </th>
              <th scope="col" className="py-1 text-start">
                {fm(rim.mode)}
              </th>
              <th scope="col" className="py-1 text-start">
                {fm(rim.nextRun)}
              </th>
              <th scope="col" className="py-1 text-start">
                {fm(rim.lastRun)}
              </th>
              <th scope="col" className="py-1 text-start">
                {fm(rim.statusColumn)}
              </th>
              <th scope="col" className="py-1 text-end">
                {fm(rim.generatedColumn)}
              </th>
            </tr>
          </thead>
          <tbody>
            {page.results.map((item) => {
              const rule = readRule(item.rrule);
              return (
                <tr key={item.id} className="border-t border-border" data-template={item.id}>
                  <td className="py-2">
                    <Link
                      href={recurringUrl(org, item.id)}
                      className="font-medium text-fg-link underline"
                    >
                      {item.name}
                    </Link>
                  </td>
                  <td className="py-2">{item.customer.name}</td>
                  <td className="py-2">
                    {fm(rim.every, { frequency: rule.frequency, n: rule.every })}
                  </td>
                  <td className="py-2">{fm(rim.modeName, { mode: item.mode })}</td>
                  <td className="py-2 tabular-nums" data-next-run="">
                    {day(item.next_run)}
                  </td>
                  <td className="py-2 tabular-nums" data-last-run="">
                    {day(item.last_run)}
                  </td>
                  <td className="py-2">
                    <Badge tone={item.status === "active" ? "success" : "neutral"}>
                      {fm(rim.status, { status: item.status })}
                    </Badge>
                  </td>
                  <td className="py-2 text-end tabular-nums" data-generated="">
                    {fm(rim.generatedCount, { created: item.generated, skipped: item.skipped })}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

/** The generated history tab (D-04-T10): every run, newest first — the invoice it created
 * (number, status, total) or the reason the date was skipped. */
export function RecurringHistory({ org, id }: Readonly<{ org: string; id: string }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [number, setNumber] = useState(1);
  const [page, setPage] = useState<Page<RecurringRun, "created" | "skipped"> | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let current = true;
    void recurringInvoicesApi
      .history(org, id, number)
      .then((r) => current && (r.status === 200 ? setPage(r.body) : setFailed(true)))
      .catch(() => current && setFailed(true));
    return () => {
      current = false;
    };
  }, [org, id, number]);

  if (failed)
    return (
      <ErrorState
        title={fm(rim.historyFailed)}
        retryLabel={fm(rim.retry)}
        onRetry={() => window.location.reload()}
      />
    );
  if (page === null) return <Skeleton className="h-48" />;
  return (
    <section aria-labelledby={`${ids}-title`} className="flex flex-col gap-3" data-history="">
      <h2 id={`${ids}-title`} className="text-lg font-semibold text-fg">
        {fm(rim.historyTitle)}
      </h2>
      <p className="text-sm text-fg-muted" data-history-counts="">
        {fm(rim.generatedCount, { created: page.counts.created, skipped: page.counts.skipped })}
      </p>
      {page.results.length === 0 ? (
        <p className="text-sm text-fg-muted">{fm(rim.historyEmpty)}</p>
      ) : (
        <table className="w-full text-sm" aria-labelledby={`${ids}-title`}>
          <thead>
            <tr className="text-xs text-fg-muted">
              <th scope="col" className="py-1 text-start">
                {fm(rim.historyDate)}
              </th>
              <th scope="col" className="py-1 text-start">
                {fm(rim.historyOutcome)}
              </th>
              <th scope="col" className="py-1 text-start">
                {fm(rim.historyInvoice)}
              </th>
              <th scope="col" className="py-1 text-end">
                {fm(rim.previewTotal)}
              </th>
            </tr>
          </thead>
          <tbody>
            {page.results.map((run) => (
              <tr key={run.date} className="border-t border-border align-top" data-run={run.status}>
                <td className="py-2 tabular-nums">{formatDate(run.date, { locale })}</td>
                <td className="py-2">
                  <Badge tone={run.status === "created" ? "success" : "warning"}>
                    {fm(rim.runStatus, { status: run.status })}
                  </Badge>
                  {run.message ? (
                    <p className="mt-1 text-xs text-fg-muted" data-run-reason="">
                      {run.message}
                    </p>
                  ) : null}
                </td>
                <td className="py-2">
                  {run.invoice ? (
                    <Link href={run.invoice.url} className="text-fg-link underline">
                      {run.invoice.number || fm(rim.historyDraft)}
                    </Link>
                  ) : (
                    NONE
                  )}
                </td>
                <td className="py-2 text-end tabular-nums">
                  {run.invoice ? formatMoney(run.invoice.total, { locale }) : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {page.pages > 1 ? (
        <div className="flex gap-2">
          <Button
            variant="secondary"
            disabled={number <= 1}
            onClick={() => setNumber((n) => n - 1)}
          >
            {fm(rim.previous)}
          </Button>
          <Button
            variant="secondary"
            disabled={number >= page.pages}
            onClick={() => setNumber((n) => n + 1)}
          >
            {fm(rim.next)}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
