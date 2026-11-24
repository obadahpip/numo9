"use client";

/**
 * Drill-down drawer (K-01-T14, wireframe 56): the lines behind one report figure — the account
 * and period in the header with the line count and the total (equal to the figure, K-01-T05);
 * date, source document, description and amount per line, 50 a page; **Open …** goes to the
 * source document (an invoice, a bank transaction, else the journal): two clicks from a P&L figure
 * to the invoice. Export lines downloads the page as CSV.
 */
import {
  Button,
  Drawer,
  ErrorState,
  Skeleton,
  formatDate,
  formatMoney,
  type AppLocale,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { reportsApi, type DrillResult, type ReportBody } from "./api";
import { drillMessages as m } from "./messages";
import type { DrillTarget } from "./ReportRunner";

const TIME_ZONE = "America/Toronto";

/** The drill query of one figure: the row's drill keys, per column when the report gives them. */
export function drillQuery(target: DrillTarget): Record<string, string> {
  const drill = (target.row.drill ?? {}) as Record<string, unknown>;
  const perColumn = Array.isArray(drill.columns)
    ? ((drill.columns as Record<string, unknown>[])[target.column] ?? {})
    : {};
  const query: Record<string, string> = {};
  for (const [key, value] of Object.entries({ ...drill, ...perColumn })) {
    if (key !== "columns" && value !== null && value !== undefined && value !== "") {
      query[key] = Array.isArray(value) ? value.join(",") : String(value);
    }
  }
  return query;
}

const SOURCE_LINKS = {
  "sales.invoice": m.openInvoice,
  "banking.banktransaction": m.openBankTransaction,
} as const;

function sourceLink(source: DrillResult["lines"][number]["source"]) {
  if (source.url === source.journal_url) return m.openJournal;
  return SOURCE_LINKS[source.type as keyof typeof SOURCE_LINKS] ?? m.openDocument;
}

export function linesCsv(result: DrillResult): string {
  const quote = (value: string) => `"${value.replace(/"/g, '""')}"`;
  const lines = result.lines.map((line) =>
    [line.date ?? "", line.journal, line.description || line.narration, line.amount]
      .map(quote)
      .join(","),
  );
  return ["date,journal,description,amount", ...lines].join("\r\n");
}

export interface DrillDrawerProps {
  org: string;
  report: string;
  target: DrillTarget;
  body: ReportBody;
  onClose: () => void;
}

export function DrillDrawer({ org, report, target, body, onClose }: DrillDrawerProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<DrillResult | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const query = useMemo(() => drillQuery(target), [target]);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    void reportsApi.drill(org, report, { ...query, page: String(page) }).then((answer) => {
      if (cancelled) return;
      if (answer.status === 200 && Array.isArray(answer.body?.lines)) setResult(answer.body);
      else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [org, report, query, page, attempt]);

  const column = body.columns[target.column]?.label ?? "";
  const date = (value: string) => formatDate(value, { locale, timeZone: TIME_ZONE });
  const period = query.to
    ? query.from
      ? fm(m.period, { from: date(query.from), to: date(query.to) })
      : fm(m.upTo, { to: date(query.to) })
    : "";
  const csvHref = result
    ? `data:text/csv;charset=utf-8,${encodeURIComponent(`﻿${linesCsv(result)}`)}`
    : undefined;

  return (
    <Drawer
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={target.row.label}
      description={[column, period].filter(Boolean).join(" · ")}
      closeLabel={fm(m.close)}
      size="lg"
      footer={
        result && result.pages > 1 ? (
          <div className="flex w-full items-center justify-between gap-2">
            <Button size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              {fm(m.previous)}
            </Button>
            <span className="text-sm text-fg-muted" role="status">
              {fm(m.page, { page: result.page, pages: result.pages })}
            </span>
            <Button size="sm" disabled={page >= result.pages} onClick={() => setPage((p) => p + 1)}>
              {fm(m.next)}
            </Button>
          </div>
        ) : undefined
      }
    >
      {failed ? (
        <ErrorState
          title={fm(m.failed)}
          retryLabel={fm(m.retry)}
          onRetry={() => setAttempt((n) => n + 1)}
          headingLevel={2}
        />
      ) : !result ? (
        <div aria-busy="true" className="flex flex-col gap-2">
          <span className="sr-only">{fm(m.loading)}</span>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold text-fg" data-drill-summary="">
              {fm(m.summary, {
                count: result.count,
                total: formatMoney(result.total, { locale }),
              })}
            </p>
            <a
              href={csvHref}
              download={`${result.account.code}-lines.csv`}
              className="text-sm text-fg underline underline-offset-2"
            >
              {fm(m.exportLines)}
            </a>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">{fm(m.lines)}</caption>
              <thead>
                <tr className="border-b border-border text-start text-xs text-fg-muted">
                  <th scope="col" className="py-2 pe-3 text-start font-semibold">
                    {fm(m.date)}
                  </th>
                  <th scope="col" className="py-2 pe-3 text-start font-semibold">
                    {fm(m.source)}
                  </th>
                  <th scope="col" className="py-2 pe-3 text-start font-semibold">
                    {fm(m.description)}
                  </th>
                  <th scope="col" className="py-2 text-end font-semibold">
                    {fm(m.amount)}
                  </th>
                </tr>
              </thead>
              <tbody>
                {result.lines.map((line, index) => {
                  return (
                    <tr key={`${line.journal}-${index}`} className="border-b border-border">
                      <td className="py-2 pe-3 whitespace-nowrap">
                        {line.date ? date(line.date) : null}
                      </td>
                      <td className="py-2 pe-3">
                        <Link
                          href={line.source.url}
                          className="font-semibold text-fg underline underline-offset-2"
                        >
                          {fm(sourceLink(line.source))}
                        </Link>
                        {line.journal ? (
                          <span className="block text-xs text-fg-muted">
                            {fm(m.journalNumber, { number: line.journal })}
                          </span>
                        ) : null}
                      </td>
                      <td className="py-2 pe-3">
                        {line.description || line.narration}
                        {line.contact ? (
                          <span className="block text-xs text-fg-muted">{line.contact}</span>
                        ) : null}
                      </td>
                      <td className="py-2 text-end tabular-nums whitespace-nowrap">
                        {formatMoney(line.amount, { locale })}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Drawer>
  );
}
