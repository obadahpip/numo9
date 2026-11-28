"use client";

/**
 * Statement lines and import history on the bank account page (F-02-T13).
 *
 * - **Statement lines** — the lines imported from the account's statements, newest first, with a
 *   status filter (All / Uncoded / Coded / Matched / Ignored, each with its count) and the
 *   **"Uncoded" badge** = the number of UNCODED lines (`counts.uncoded` of the API). Statement
 *   lines are not in the books until they are coded or matched (F-04 / F-05).
 * - Each row has an **actions menu**: `statementLineActions` (below) lists what it offers — "Show
 *   the lines of this import" here; other features add theirs (F-04: "Create rule from line").
 * - **Import history** — each import with its counts, who and when, and **Undo** while none of
 *   its lines is coded or matched (the API refuses with the lines otherwise).
 */
import { Badge, Button, formatDate, formatMoney, type AppLocale } from "@numo9/ui";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";
import { ruleFromLineHref } from "@/banking/rules/fromLine";

import { refusalText, statementLinesApi, importsApi, type StatementImport } from "./api";
import type { StatementLine, StatementLineCounts, StatementLineStatus } from "./api";
import { lines as msg } from "./messages";

const TIME_ZONE = "America/Toronto";
const FILTERS: (StatementLineStatus | "all")[] = ["all", "uncoded", "coded", "matched", "ignored"];

/** What a statement line's actions menu can do; features push their own entries. */
export interface StatementLineAction {
  id: string;
  label: (fm: ReturnType<typeof useFormatMessage>) => string;
  run: (line: StatementLine, panel: StatementLinePanel) => void;
}

/** What an action can ask of the panel. */
export interface StatementLinePanel {
  showImport: (id: string, name: string) => void;
  /** Open the rule builder pre-filled from the line (F-04-T14). */
  createRule: (line: StatementLine) => void;
}

export const statementLineActions: StatementLineAction[] = [
  {
    id: "show-import",
    label: (fm) => fm(msg.showImport),
    run: (line, panel) => {
      if (line.import) panel.showImport(line.import.id, line.import.file_name);
    },
  },
  {
    id: "create-rule",
    label: (fm) => fm(msg.createRule),
    run: (line, panel) => panel.createRule(line),
  },
];

export function StatementPanel({
  org,
  account,
  currency,
  actions = statementLineActions,
}: {
  org: string;
  account: string;
  currency: string;
  actions?: StatementLineAction[];
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [status, setStatus] = useState<StatementLineStatus | "all">("all");
  const [fromImport, setFromImport] = useState<{ id: string; name: string } | null>(null);
  const [rows, setRows] = useState<StatementLine[] | null>(null);
  const [counts, setCounts] = useState<StatementLineCounts | null>(null);
  const [total, setTotal] = useState(0);
  const [history, setHistory] = useState<StatementImport[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [notice, setNotice] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void statementLinesApi
      .list(org, account, {
        status: status === "all" ? undefined : status,
        import: fromImport?.id,
      })
      .then((result) => {
        if (cancelled) return;
        if (result.status === 200 && Array.isArray(result.body?.results) && result.body.counts) {
          setRows(result.body.results);
          setCounts(result.body.counts);
          setTotal(result.body.count);
          setFailed(false);
        } else setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [org, account, status, fromImport, refresh]);

  useEffect(() => {
    let cancelled = false;
    void importsApi.history(org, account).then((result) => {
      if (!cancelled && result.status === 200 && Array.isArray(result.body?.results))
        setHistory(result.body.results);
    });
    return () => {
      cancelled = true;
    };
  }, [org, account, refresh]);

  const money = (value: string) => formatMoney(value, { locale, currency });
  const day = (value: string | null) =>
    value ? formatDate(value, { locale, timeZone: TIME_ZONE }) : "";
  const filterLabel: Record<StatementLineStatus | "all", string> = {
    all: fm(msg.all),
    uncoded: fm(msg.uncoded),
    coded: fm(msg.coded),
    matched: fm(msg.matched),
    ignored: fm(msg.ignored),
  };

  const undo = async (item: StatementImport) => {
    const result = await importsApi.undo(org, account, item.id);
    setNotice(
      result.status === 200
        ? fm(msg.undone, { file: item.file_name })
        : fm(msg.undoRefused, { file: item.file_name, reason: refusalText(result.body) ?? "" }),
    );
    setRefresh((n) => n + 1);
  };

  const router = useRouter();
  const panel: StatementLinePanel = {
    createRule: (line: StatementLine) => {
      setOpen(null);
      router.push(ruleFromLineHref(org, { ...line, bank_account: account }));
    },
    showImport: (id: string, name: string) => {
      setFromImport({ id, name });
      setStatus("all");
      setOpen(null);
    },
  };

  return (
    <div className="flex flex-col gap-8" data-statement-panel="">
      <section aria-labelledby={`${ids}-lines`} className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <h2 id={`${ids}-lines`} className="text-lg font-semibold text-fg">
            {fm(msg.title)}
          </h2>
          {counts ? (
            <Badge tone={counts.uncoded ? "warning" : "neutral"}>
              <span data-uncoded-badge="">{fm(msg.uncodedBadge, { count: counts.uncoded })}</span>
            </Badge>
          ) : null}
        </div>
        <div role="group" aria-label={fm(msg.filter)} className="flex flex-wrap gap-2">
          {FILTERS.map((value) => (
            <Button
              key={value}
              size="sm"
              variant={status === value ? "primary" : "secondary"}
              aria-pressed={status === value}
              onClick={() => setStatus(value)}
            >
              {fm(msg.filterItem, {
                label: filterLabel[value],
                count: counts ? counts[value] : 0,
              })}
            </Button>
          ))}
        </div>
        {fromImport ? (
          <p className="flex flex-wrap items-center gap-2 text-sm">
            {fm(msg.showingImport, { file: fromImport.name })}
            <Button size="sm" variant="ghost" onClick={() => setFromImport(null)}>
              {fm(msg.allLines)}
            </Button>
          </p>
        ) : null}
        {failed ? (
          <p role="alert" className="text-sm text-fg-danger">
            {fm(msg.failed)}
          </p>
        ) : rows === null ? (
          <p className="text-sm text-fg-muted">{fm(msg.loading)}</p>
        ) : rows.length === 0 ? (
          counts && counts.all === 0 ? (
            <div className="rounded-md border border-border p-4 text-sm" data-lines-empty="">
              <p className="font-semibold">{fm(msg.empty)}</p>
              <p className="text-fg-muted">{fm(msg.emptyBody)}</p>
            </div>
          ) : (
            <p className="text-sm text-fg-muted">{fm(msg.noMatch)}</p>
          )
        ) : (
          <div className="overflow-x-auto">
            {rows.length < total ? (
              <p className="text-xs text-fg-muted">{fm(msg.more, { shown: rows.length, total })}</p>
            ) : null}
            <table
              className="min-w-full text-sm"
              aria-labelledby={`${ids}-lines`}
              data-statement-lines=""
            >
              <thead>
                <tr className="text-xs text-fg-muted">
                  <th scope="col" className="p-2 text-start">
                    {fm(msg.colDate)}
                  </th>
                  <th scope="col" className="p-2 text-start">
                    {fm(msg.colDescription)}
                  </th>
                  <th scope="col" className="p-2 text-start">
                    {fm(msg.colReference)}
                  </th>
                  <th scope="col" className="p-2 text-end">
                    {fm(msg.colAmount)}
                  </th>
                  <th scope="col" className="p-2 text-start">
                    {fm(msg.colStatus)}
                  </th>
                  <th scope="col" className="p-2 text-end">
                    {fm(msg.colActions)}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((line) => (
                  <tr
                    key={line.id}
                    className="border-t border-border"
                    data-statement-line={line.status}
                  >
                    <td className="p-2 tabular-nums">{day(line.date)}</td>
                    <td className="p-2">
                      {line.description}
                      {line.payee && line.payee !== line.description ? (
                        <span className="block text-xs text-fg-muted">{line.payee}</span>
                      ) : null}
                    </td>
                    <td className="p-2">{line.reference || line.fitid}</td>
                    <td
                      className={[
                        "p-2 text-end tabular-nums",
                        line.amount.startsWith("-") ? "" : "text-fg-success",
                      ].join(" ")}
                    >
                      {money(line.amount)}
                    </td>
                    <td className="p-2">
                      <Badge tone={line.status === "uncoded" ? "warning" : "neutral"}>
                        {line.status_label}
                      </Badge>
                    </td>
                    <td className="relative p-2 text-end" data-line-actions="">
                      <Button
                        size="sm"
                        variant="ghost"
                        aria-expanded={open === line.id}
                        aria-controls={`${ids}-menu-${line.id}`}
                        aria-label={fm(msg.actionsFor, {
                          date: day(line.date),
                          description: line.description,
                        })}
                        onClick={() => setOpen(open === line.id ? null : line.id)}
                      >
                        {fm(msg.actions)}
                      </Button>
                      {open === line.id ? (
                        <ul
                          id={`${ids}-menu-${line.id}`}
                          className="absolute end-2 z-10 mt-1 flex min-w-56 flex-col rounded-md border border-border bg-surface p-1 text-start shadow-elevation-1"
                        >
                          {actions.map((action) => (
                            <li key={action.id}>
                              <button
                                type="button"
                                className="w-full rounded px-3 py-2 text-start text-sm hover:bg-surface-accent"
                                onClick={() => {
                                  setOpen(null);
                                  action.run(line, panel);
                                }}
                              >
                                {action.label(fm)}
                              </button>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby={`${ids}-history`} className="flex flex-col gap-3">
        <h2 id={`${ids}-history`} className="text-lg font-semibold text-fg">
          {fm(msg.historyTitle)}
        </h2>
        {notice ? (
          <p role="status" className="text-sm" data-history-notice="">
            {notice}
          </p>
        ) : null}
        {history === null ? null : history.length === 0 ? (
          <p className="text-sm text-fg-muted">{fm(msg.historyEmpty)}</p>
        ) : (
          <div className="overflow-x-auto">
            <table
              className="min-w-full text-sm"
              aria-labelledby={`${ids}-history`}
              data-import-history=""
            >
              <thead>
                <tr className="text-xs text-fg-muted">
                  <th scope="col" className="p-2 text-start">
                    {fm(msg.colFile)}
                  </th>
                  <th scope="col" className="p-2 text-start">
                    {fm(msg.colImported)}
                  </th>
                  <th scope="col" className="p-2 text-start">
                    {fm(msg.colStatus)}
                  </th>
                  <th scope="col" className="p-2 text-end">
                    {fm(msg.colNew)}
                  </th>
                  <th scope="col" className="p-2 text-end">
                    {fm(msg.colDuplicates)}
                  </th>
                  <th scope="col" className="p-2 text-end">
                    {fm(msg.colErrors)}
                  </th>
                  <th scope="col" className="p-2 text-end">
                    {fm(msg.colActions)}
                  </th>
                </tr>
              </thead>
              <tbody>
                {history.map((item) => (
                  <tr
                    key={item.id}
                    className="border-t border-border"
                    data-import-row={item.status}
                  >
                    <td className="p-2">
                      {item.file_name}
                      <span className="block text-xs text-fg-muted">
                        {[item.file_format.toUpperCase(), item.mapping?.name]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </td>
                    <td className="p-2">
                      {formatDate(new Date(item.committed_at ?? item.created_at), {
                        locale,
                        timeZone: TIME_ZONE,
                      })}
                      {item.created_by ? (
                        <span className="block text-xs text-fg-muted">{item.created_by.name}</span>
                      ) : null}
                    </td>
                    <td className="p-2">{item.status_label}</td>
                    <td className="p-2 text-end tabular-nums">{item.counts.new}</td>
                    <td className="p-2 text-end tabular-nums">{item.counts.duplicate}</td>
                    <td className="p-2 text-end tabular-nums">{item.counts.error}</td>
                    <td className="p-2 text-end">
                      {item.status === "committed" ? (
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={item.can_undo === false}
                          title={item.can_undo === false ? fm(msg.undoBlocked) : undefined}
                          aria-label={fm(msg.undoFile, { file: item.file_name })}
                          onClick={() => void undo(item)}
                        >
                          {fm(msg.undo)}
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
