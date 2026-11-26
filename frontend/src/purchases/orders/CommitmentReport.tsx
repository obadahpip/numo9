"use client";

/**
 * Commitment report (E-01-T14): open PO value — ordered on approved purchase orders and not
 * billed yet, before tax — grouped by account, supplier or month of the PO date, with a date
 * range, the number of open POs and lines per row, the total, and a budget column kept empty
 * until budgets (K-04). **Export CSV / Excel** download the same query from the server, so the
 * file has the screen's rows, in the screen's order, and its total (E-01-T08 query).
 */
import { ErrorState, Input, SkeletonTable, formatMoney, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import {
  commitmentsApi,
  type CommitmentGrouping,
  type CommitmentQuery,
  type CommitmentReport as Report,
} from "./api";
import { commitments as m } from "./messages";

const GROUPS: readonly CommitmentGrouping[] = ["account", "supplier", "month"];

export function CommitmentReport({ org }: { org: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [by, setBy] = useState<CommitmentGrouping>("account");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const query: CommitmentQuery = { by, ...(from ? { from } : {}), ...(to ? { to } : {}) };
  const key = JSON.stringify(query);

  useEffect(() => {
    let cancelled = false;
    setReport(null);
    void commitmentsApi.get(org, JSON.parse(key) as CommitmentQuery).then((result) => {
      if (cancelled) return;
      if (result.status === 200 && Array.isArray(result.body.rows)) {
        setReport(result.body);
        setFailed(false);
      } else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [org, key, attempt]);

  const groupLabel = { account: m.byAccount, supplier: m.bySupplier, month: m.byMonth };
  const field = "flex flex-col gap-1 text-sm font-medium text-fg";
  const head = "px-3 py-2 text-end text-xs font-semibold text-fg-muted";
  const cell = "px-3 py-2 text-end tabular-nums";
  const link = "rounded-md border border-border px-3 py-1.5 text-sm font-medium text-fg";

  return (
    <section aria-labelledby={`${ids}-title`} className="flex flex-col gap-4" data-commitments="">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h1 id={`${ids}-title`} className="text-2xl font-semibold text-fg">
          {fm(m.title)}
        </h1>
        <a href={`/o/${org}/purchases/orders`} className="text-sm text-fg underline">
          {fm(m.back)}
        </a>
      </div>
      <p className="max-w-prose text-sm text-fg-muted">{fm(m.intro)}</p>
      <div className="flex flex-wrap items-end gap-4">
        <label className={field}>
          {fm(m.by)}
          <select
            value={by}
            onChange={(e) => setBy(e.target.value as CommitmentGrouping)}
            className="min-h-touch-target rounded-md border border-border bg-surface px-2 text-sm text-fg"
          >
            {GROUPS.map((group) => (
              <option key={group} value={group}>
                {fm(groupLabel[group])}
              </option>
            ))}
          </select>
        </label>
        <label className={field}>
          {fm(m.from)}
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label className={field}>
          {fm(m.to)}
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
        <div className="flex gap-2">
          <a href={commitmentsApi.exportUrl(org, query, "csv")} download className={link}>
            {fm(m.exportCsv)}
          </a>
          <a href={commitmentsApi.exportUrl(org, query, "xlsx")} download className={link}>
            {fm(m.exportXlsx)}
          </a>
        </div>
      </div>
      {failed ? (
        <ErrorState
          title={fm(m.loadFailed)}
          retryLabel={fm(m.retry)}
          onRetry={() => setAttempt((n) => n + 1)}
        />
      ) : !report ? (
        <SkeletonTable rows={4} columns={5} />
      ) : report.rows.length === 0 ? (
        <p className="p-6 text-center text-sm text-fg-muted">{fm(m.empty)}</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-sm" aria-labelledby={`${ids}-title`}>
            <thead className="bg-surface-muted">
              <tr>
                <th
                  scope="col"
                  className="px-3 py-2 text-start text-xs font-semibold text-fg-muted"
                >
                  {fm(groupLabel[report.by])}
                </th>
                <th scope="col" className={head}>
                  {fm(m.orders)}
                </th>
                <th scope="col" className={head}>
                  {fm(m.lines)}
                </th>
                <th scope="col" className={head}>
                  {fm(m.amount)}
                </th>
                <th scope="col" className={head}>
                  {fm(m.budget)}
                </th>
              </tr>
            </thead>
            <tbody>
              {report.rows.map((row) => (
                <tr key={row.key || "none"} className="border-t border-border">
                  <th scope="row" className="px-3 py-2 text-start font-normal">
                    {row.label || fm(m.noAccount)}
                  </th>
                  <td className={cell}>{row.orders}</td>
                  <td className={cell}>{row.lines}</td>
                  <td className={cell}>{formatMoney(row.amount, { locale })}</td>
                  <td className={cell}>
                    {row.budget === null ? "" : formatMoney(row.budget, { locale })}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-border font-semibold">
                <th scope="row" className="px-3 py-2 text-start">
                  {fm(m.total)}
                </th>
                <td className={cell} />
                <td className={cell} />
                <td className={cell} data-total="">
                  {formatMoney(report.total, { locale })}
                </td>
                <td className={cell} />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
      <p className="text-xs text-fg-muted">{fm(m.budgetLater)}</p>
    </section>
  );
}
