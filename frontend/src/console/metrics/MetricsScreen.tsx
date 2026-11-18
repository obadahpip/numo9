"use client";

/**
 * Console → Metrics (U-06-T06): KPI tiles (MRR, active organisations, trials, conversion and
 * churn over 30 days — demo organisations never counted), a Recharts trend of the selected
 * metric over 30/90/365 days, and each count tile's drill-down: the organisations it counts, so
 * the tile's number and the list always agree (the API answers both from the same query).
 */
import { Button, ErrorState, formatDate, formatMoney, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useFormatMessage, type MessageDescriptor } from "@/i18n";

import type { PlatformOrganisationPage } from "../organisations/api";
import {
  drillDown,
  getMetrics,
  type DrillMetric,
  type MetricPoint,
  type PlatformMetrics,
} from "./api";
import { m } from "./messages";
import { TrendChart } from "./TrendChart";

type Metric = "mrr" | "active" | "trials" | "conversion" | "churn";

const LABELS: Record<Metric, MessageDescriptor> = {
  mrr: m.mrr,
  active: m.active,
  trials: m.trials,
  conversion: m.conversion,
  churn: m.churn,
};
const DRILLABLE: Metric[] = ["mrr", "active", "trials"];
const PERIODS = [30, 90, 365];

function valueOf(point: MetricPoint, metric: Metric): number | null {
  switch (metric) {
    case "mrr":
      return point.mrr_cents;
    case "active":
      return point.active;
    case "trials":
      return point.trials;
    case "conversion":
      return point.conversion_rate === null ? null : Number(point.conversion_rate);
    case "churn":
      return point.churn_rate === null ? null : Number(point.churn_rate);
  }
}

export function MetricsScreen() {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [days, setDays] = useState(90);
  const [data, setData] = useState<PlatformMetrics | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [selected, setSelected] = useState<Metric>("mrr");
  const [drill, setDrill] = useState<DrillMetric | null>(null);
  const [list, setList] = useState<PlatformOrganisationPage | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getMetrics(days).then((result) => {
      if (cancelled) return;
      if (result.status === 200) {
        setData(result.body);
        setFailed(false);
      } else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [days, attempt]);

  useEffect(() => {
    if (drill === null) return;
    let cancelled = false;
    setList(null);
    void drillDown(drill).then((result) => {
      if (!cancelled && result.status === 200) setList(result.body);
    });
    return () => {
      cancelled = true;
    };
  }, [drill]);

  const money = (cents: number) =>
    formatMoney((cents / 100).toFixed(2), { locale, fractionDigits: 2 });
  const percent = (rate: number) =>
    new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 1 }).format(rate);
  const show = (metric: Metric, value: number | null): string => {
    if (value === null) return fm(m.noRate);
    if (metric === "mrr") return money(value);
    if (metric === "conversion" || metric === "churn") return percent(value);
    return new Intl.NumberFormat(locale).format(value);
  };
  const day = (iso: string) => formatDate(iso as never, { locale });

  if (failed) {
    return (
      <ErrorState
        title={fm(m.loadFailed)}
        retryLabel={fm(m.retry)}
        onRetry={() => setAttempt((n) => n + 1)}
        headingLevel={2}
      />
    );
  }

  const current = data?.current;
  const detail = (metric: Metric): string | null => {
    if (!current) return null;
    if (metric === "conversion")
      return fm(m.conversionDetail, { converted: current.converted, ended: current.trials_ended });
    if (metric === "churn")
      return fm(m.churnDetail, { cancelled: current.cancelled, base: current.active_at_start });
    return null;
  };

  return (
    <div className="flex flex-col gap-6" data-console-metrics="">
      <div>
        <h1 className="text-2xl font-bold text-fg">{fm(m.title)}</h1>
        <p className="text-sm text-fg-muted">{fm(m.demoNote)}</p>
      </div>
      {current ? (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {(Object.keys(LABELS) as Metric[]).map((metric) => (
            <li
              key={metric}
              data-tile={metric}
              className={`flex flex-col gap-2 rounded-lg border p-4 ${
                selected === metric ? "border-border-accent" : "border-border"
              }`}
            >
              <button
                type="button"
                className="flex flex-col items-start gap-1 text-start"
                aria-pressed={selected === metric}
                onClick={() => setSelected(metric)}
              >
                <span className="text-xs font-semibold text-fg-muted">{fm(LABELS[metric])}</span>
                <span className="text-2xl font-bold text-fg" data-tile-value="">
                  {show(metric, valueOf(current, metric))}
                </span>
              </button>
              {detail(metric) ? (
                <span className="text-xs text-fg-muted">{detail(metric)}</span>
              ) : null}
              {DRILLABLE.includes(metric) ? (
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={fm(m.showListFor, { metric: fm(LABELS[metric]) })}
                  onClick={() => setDrill(metric as DrillMetric)}
                >
                  {fm(m.showList)}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {data ? (
        <section className="flex flex-col gap-3" aria-labelledby="console-metrics-trend">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="console-metrics-trend" className="text-lg font-semibold text-fg">
              {fm(m.trend, { metric: fm(LABELS[selected]) })}
            </h2>
            <div role="group" aria-label={fm(m.range)} className="flex gap-1">
              {PERIODS.map((period) => (
                <Button
                  key={period}
                  size="sm"
                  variant={period === days ? "primary" : "secondary"}
                  aria-pressed={period === days}
                  onClick={() => setDays(period)}
                >
                  {fm(m.days, { days: period })}
                </Button>
              ))}
            </div>
          </div>
          <TrendChart
            label={fm(m.chartLabel, { metric: fm(LABELS[selected]), days })}
            points={data.history.map((point) => ({
              date: point.date,
              value: valueOf(point, selected),
            }))}
            format={(value) => show(selected, value)}
            formatDate={day}
          />
          <details>
            <summary className="cursor-pointer text-sm text-fg-link">{fm(m.dataTable)}</summary>
            <table className="mt-2 w-full text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-fg-muted">
                  <th className="py-1 text-start">{fm(m.date)}</th>
                  <th className="py-1 text-end">{fm(m.value)}</th>
                </tr>
              </thead>
              <tbody>
                {data.history.map((point) => (
                  <tr key={point.date} className="border-b border-border">
                    <td className="py-1">{day(point.date)}</td>
                    <td className="py-1 text-end">{show(selected, valueOf(point, selected))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </section>
      ) : null}

      {drill && list ? (
        <section
          className="flex flex-col gap-2"
          aria-labelledby="console-metrics-drill"
          data-drill={drill}
        >
          <h2 id="console-metrics-drill" className="text-lg font-semibold text-fg">
            {fm(m.drillTitle, { metric: fm(LABELS[drill]), count: list.count })}
          </h2>
          <ul className="flex flex-col divide-y divide-border">
            {list.results.map((row) => (
              <li key={row.id} className="py-2" data-org={row.id}>
                <Link href={`/console/organisations/${row.id}`} className="text-fg underline">
                  {row.name}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
