"use client";

/**
 * Contact → Statements (B-02-T11): choose outstanding or activity and the dates, preview the lines
 * (the same data the PDF prints), open the PDF, email it; statements sent before.
 */
import {
  Button,
  formatDate,
  formatMoney,
  Input,
  RadioGroup,
  todayIn,
  type AppLocale,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { firstError } from "./api";
import {
  activityApi,
  type SentStatement,
  type StatementData,
  type StatementQuery,
} from "./activityApi";
import { tm } from "./tabMessages";

export function StatementsTab({ org, id }: { org: string; id: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [query, setQuery] = useState<StatementQuery>({ kind: "outstanding", as_at: todayIn() });
  const [data, setData] = useState<StatementData | null>(null);
  const [history, setHistory] = useState<SentStatement[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const loadHistory = useCallback(async () => {
    const result = await activityApi.history(org, id);
    if (result.status === 200) setHistory(result.body.results);
  }, [org, id]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const preview = async () => {
    const result = await activityApi.statement(org, id, query);
    if (result.status === 200) {
      setData(result.body);
      setError("");
    } else {
      setError(fm(tm.failed, { reason: firstError(result.body) ?? "" }));
    }
  };

  const send = async () => {
    const result = await activityApi.send(org, id, query);
    if (result.status === 201) {
      setStatus(fm(tm.sent, { to: result.body.recipients.join(", ") }));
      setError("");
      void loadHistory();
    } else {
      setError(fm(tm.failed, { reason: firstError(result.body) ?? "" }));
    }
  };

  const money = (amount: string) => formatMoney(amount, { locale });
  const date = (value: string | null) => (value ? formatDate(value, { locale }) : "—");

  return (
    <div className="flex flex-col gap-4" data-statements-tab="">
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1 text-sm">
          <span id="statement-kind">{fm(tm.kind)}</span>
          <RadioGroup
            aria-labelledby="statement-kind"
            value={query.kind}
            onValueChange={(value) =>
              setQuery((q) => ({ ...q, kind: value as StatementQuery["kind"] }))
            }
            options={[
              { value: "outstanding", label: fm(tm.outstanding) },
              { value: "activity", label: fm(tm.activityKind) },
            ]}
          />
        </div>
        {query.kind === "activity" ? (
          <label className="flex flex-col gap-1 text-sm">
            {fm(tm.from)}
            <Input
              type="date"
              value={query.from ?? ""}
              onChange={(e) => setQuery((q) => ({ ...q, from: e.target.value }))}
            />
          </label>
        ) : null}
        <label className="flex flex-col gap-1 text-sm">
          {fm(tm.asAt)}
          <Input
            type="date"
            value={query.as_at}
            onChange={(e) => setQuery((q) => ({ ...q, as_at: e.target.value }))}
          />
        </label>
        <Button onClick={() => void preview()}>{fm(tm.preview)}</Button>
        <a
          href={activityApi.pdfUrl(org, id, query)}
          target="_blank"
          rel="noreferrer"
          className="text-sm font-semibold underline"
        >
          {fm(tm.pdf)}
        </a>
        <Button variant="primary" onClick={() => void send()}>
          {fm(tm.send)}
        </Button>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <p role="status" className="text-sm text-fg-muted">
        {status}
      </p>
      {data ? (
        <section className="flex flex-col gap-2" data-statement-preview="">
          {data.kind === "activity" ? (
            <p className="text-sm">{fm(tm.opening, { amount: money(data.opening_balance) })}</p>
          ) : null}
          <ul className="flex flex-col divide-y divide-border rounded-md border border-border text-sm">
            <li className="grid grid-cols-5 gap-2 p-2 font-semibold" aria-hidden="true">
              <span>{fm(tm.colDate)}</span>
              <span>{fm(tm.colDocument)}</span>
              <span>{fm(tm.colDue)}</span>
              <span className="text-end">{fm(tm.colAmount)}</span>
              <span className="text-end">{fm(tm.colBalance)}</span>
            </li>
            {data.lines.map((line) => (
              <li
                key={`${line.document}-${line.date}-${line.balance}`}
                className="grid grid-cols-5 gap-2 p-2"
              >
                <span>{date(line.date)}</span>
                <span>{line.document}</span>
                <span>{date(line.due_date)}</span>
                <span className="text-end tabular-nums">{money(line.amount)}</span>
                <span className="text-end tabular-nums">{money(line.balance)}</span>
              </li>
            ))}
          </ul>
          <p className="text-end text-base font-semibold" data-amount-due="">
            {fm(tm.amountDue, { amount: money(data.amount_due) })}
          </p>
        </section>
      ) : null}
      {history.length > 0 ? (
        <section className="flex flex-col gap-1">
          <h3 className="text-sm font-semibold">{fm(tm.history)}</h3>
          <ul className="text-sm text-fg-muted">
            {history.map((row) => (
              <li key={row.id}>
                {fm(tm.historyLine, {
                  date: date(row.sent_at.slice(0, 10)),
                  as_at: date(row.as_at),
                  amount: money(row.amount_due),
                  to: row.recipients.join(", "),
                })}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
