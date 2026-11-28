"use client";

/**
 * Activity tab of Assurance (K-09-T24, wireframe A5): the user-activity heatmap from the audit
 * log (`GET assurance/heatmap`, K-09-T19) — a calendar grid of the last 12 months, one square per
 * day in the organisation's time zone shaded by its count (single-hue sequential scale, a Less →
 * More legend, a tooltip per day), a person filter, the people with their totals and last
 * activity (a dormant administrator stands out), and *Show as table*: the accessible equivalent
 * (date and count of every day with activity), keyboard reachable. The grid itself is one image
 * to assistive technology, named by its summary; the table carries the numbers.
 */
import { Button, EmptyState, ErrorState, formatDate, INPUT_BASE, type AppLocale } from "@numo9/ui";
import { useEffect, useId, useMemo, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { assuranceApi, type Heatmap } from "./api";
import { calendar, type HeatCell } from "./heatCalendar";
import { am } from "./messages";

/** Single-hue sequential ramp (accent), light → dark; 0 is the neutral surface. */
const SHADES: Record<HeatCell["level"], string> = {
  0: "bg-surface-muted",
  1: "bg-surface-accent/25",
  2: "bg-surface-accent/50",
  3: "bg-surface-accent/75",
  4: "bg-surface-accent",
};

export function ActivityHeatmap({ org, locale }: { org: string; locale: AppLocale }) {
  const fm = useFormatMessage();
  const ids = useId();
  const [person, setPerson] = useState("");
  const [data, setData] = useState<Heatmap | null>(null);
  const [everyone, setEveryone] = useState<Heatmap["people"]>([]);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [table, setTable] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    void assuranceApi
      .heatmap(org, { days: 365, user: person })
      .catch(() => null)
      .then((answer) => {
        if (cancelled) return;
        if (answer?.status === 200 && Array.isArray(answer.body?.days)) {
          setData(answer.body);
          if (!person) setEveryone(answer.body.people);
        } else setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [org, person, attempt]);

  const weeks = useMemo(() => (data ? calendar(data.from, data.to, data.days) : []), [data]);
  const day = (date: string) => formatDate(date, { locale });
  const month = (key: string) =>
    new Intl.DateTimeFormat(locale, { month: "short", timeZone: "UTC" }).format(
      new Date(`${key}-01T00:00:00Z`),
    );

  if (failed) {
    return (
      <ErrorState
        title={fm(am.activityFailed)}
        retryLabel={fm(am.retry)}
        onRetry={() => setAttempt((n) => n + 1)}
      />
    );
  }
  if (!data) return null;

  const summary = fm(am.heatSummary, { total: data.total, from: day(data.from), to: day(data.to) });

  return (
    <section className="flex flex-col gap-4" data-heatmap={data.total}>
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-fg">{fm(am.activityTitle)}</h2>
          <p className="text-sm text-fg-muted">{fm(am.activityHelp, { zone: data.time_zone })}</p>
        </div>
        <label className="flex flex-col gap-1 text-sm text-fg" htmlFor={`${ids}-person`}>
          {fm(am.person)}
          <select
            id={`${ids}-person`}
            className={`${INPUT_BASE} border-border`}
            value={person}
            onChange={(event) => setPerson(event.target.value)}
          >
            <option value="">{fm(am.everyone)}</option>
            {everyone.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      </header>

      <div className="overflow-x-auto">
        <div role="img" aria-label={summary} className="inline-flex gap-1" data-heatmap-grid="">
          <div aria-hidden="true" className="flex flex-col gap-0.5 pt-4 pe-1 text-xs text-fg-muted">
            {[0, 1, 2, 3, 4, 5, 6].map((d) => (
              <span key={d} className="h-3 leading-3">
                {d % 2 === 0 ? fm(am.weekday, { day: String(d) }) : ""}
              </span>
            ))}
          </div>
          {weeks.map((week, w) => (
            <div key={w} className="flex flex-col gap-0.5" aria-hidden="true">
              <span className="h-4 text-xs whitespace-nowrap text-fg-muted">
                {week.month ? month(week.month) : ""}
              </span>
              {week.days.map((cell, d) =>
                cell ? (
                  <span
                    key={cell.date}
                    title={fm(am.heatCell, { date: day(cell.date), count: cell.count })}
                    data-day={cell.date}
                    data-count={cell.count}
                    data-level={cell.level}
                    className={`size-3 rounded-sm ${SHADES[cell.level]}`}
                  />
                ) : (
                  <span key={`empty-${d}`} className="size-3" />
                ),
              )}
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p aria-hidden="true" className="flex items-center gap-1 text-xs text-fg-muted">
          {fm(am.less)}
          {([0, 1, 2, 3, 4] as const).map((level) => (
            <span key={level} className={`size-3 rounded-sm ${SHADES[level]}`} />
          ))}
          {fm(am.more)}
        </p>
        <Button
          size="sm"
          variant="secondary"
          aria-expanded={table}
          aria-controls={`${ids}-table`}
          onClick={() => setTable((shown) => !shown)}
        >
          {table ? fm(am.hideTable) : fm(am.showTable)}
        </Button>
      </div>
      {table ? (
        data.days.length ? (
          <table id={`${ids}-table`} className="w-full max-w-md text-sm" data-heatmap-table="">
            <caption className="pb-1 text-start text-sm text-fg-muted">{summary}</caption>
            <thead>
              <tr className="text-xs text-fg-muted">
                <th scope="col" className="py-1 text-start">
                  {fm(am.dayColumn)}
                </th>
                <th scope="col" className="py-1 text-end">
                  {fm(am.actionsColumn)}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.days.map((d) => (
                <tr key={d.date} className="border-t border-border">
                  <td className="py-1">{day(d.date)}</td>
                  <td className="py-1 text-end tabular-nums">{d.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div id={`${ids}-table`}>
            <EmptyState title={fm(am.noActivity)} compact />
          </div>
        )
      ) : null}

      <section className="flex flex-col gap-1" aria-labelledby={`${ids}-people`}>
        <h3 id={`${ids}-people`} className="text-sm font-semibold text-fg">
          {fm(am.peopleTitle)}
        </h3>
        {data.people.length ? (
          <table className="w-full max-w-xl text-sm" data-heatmap-people="">
            <thead>
              <tr className="text-xs text-fg-muted">
                <th scope="col" className="py-1 text-start">
                  {fm(am.person)}
                </th>
                <th scope="col" className="py-1 text-end">
                  {fm(am.actionsColumn)}
                </th>
                <th scope="col" className="py-1 text-end">
                  {fm(am.lastColumn)}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.people.map((p) => (
                <tr key={p.id} className="border-t border-border" data-person={p.id}>
                  <td className="py-1">{p.name}</td>
                  <td className="py-1 text-end tabular-nums">{p.count}</td>
                  <td className="py-1 text-end">
                    {p.last
                      ? formatDate(new Date(p.last), { locale, timeZone: data.time_zone })
                      : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-fg-muted">{fm(am.noActivity)}</p>
        )}
      </section>
    </section>
  );
}
