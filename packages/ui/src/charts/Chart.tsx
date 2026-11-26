"use client";

/**
 * Bar and line charts (K-05-T08) for the dashboard and reports — pure SVG like the activity
 * heatmap (no chart library in the design system), so the rules below hold by construction:
 *
 * - **Zero rendering rule (gap-60)** — the value axis always includes 0 and is drawn from real
 *   tick labels: an empty or all-zero chart shows `$0` (and `$1`), never "—k" or a blank plot.
 *   Negative values go below the zero line, which stays the baseline.
 * - **CAD axis format** — compact Canadian dollars in the locale: `$0`, `$5K`, `$12.5K`, `$1.2M`
 *   (fr-CA `0 $`, `5 k $`); exact amounts (`$1,234.56`) in tooltips and the table.
 * - **Table fallback** — "Show as table" swaps the chart for a table of the exact amounts (every
 *   category, `$0.00` for empty ones): the accessible alternative and the print view.
 * - **One axis**, at most two series in the fixed order (blue, then amber — validated categorical
 *   pair, never cycled); a legend for two series, none for one (the title names it); thin marks
 *   (2 px lines, ≥ 8 px markers, bars with 4 px rounded data ends and 2 px gaps); recessive grid.
 *
 * Every text comes from the caller (`labels`); amounts are decimal strings or numbers.
 */
import { useId, useMemo, useState, type ReactNode } from "react";

import { formatMoney, type Amount } from "../format/format";
import { intlLocale, type AppLocale } from "../format/locale";
import { cn } from "../primitives/cn";

/** Series fills, in order (validated: CVD ΔE 28.6, both ≥ 3:1 on the surface). */
export const CHART_SERIES = ["var(--color-blue-700)", "var(--color-amber-700)"] as const;

export interface ChartCategory {
  key: string;
  /** Axis and table label, e.g. "Jun" / "June 2026". */
  label: string;
}

export interface ChartSeries {
  key: string;
  label: string;
  /** One value per category, in the categories' order (missing → 0). */
  values: Amount[];
}

export interface ChartLabels {
  /** Accessible name of the chart: "Cash in and out, last 6 months". */
  chart: string;
  showTable: string;
  showChart: string;
  /** Heading of the table's category column, e.g. "Month". */
  category: string;
  /** Tooltip of one point: (series, category, amount) → "Money in, Jun: $1,250.00". */
  point?: (series: string, category: string, amount: string) => string;
}

export interface ChartProps {
  categories: ChartCategory[];
  series: ChartSeries[];
  locale: AppLocale;
  labels: ChartLabels;
  /** Drawing height in px (default 200); the width follows the container. */
  height?: number;
  className?: string;
}

// ---- scale -------------------------------------------------------------------------------------

function toNumber(value: Amount | undefined): number {
  const n = Number(value ?? 0);
  return Number.isFinite(n) ? n : 0;
}

/**
 * Value-axis ticks: "nice" steps (1, 2, 2.5, 5 × 10ⁿ) from ≤ min to ≥ max, **always including 0**.
 * All zero (or no data) → `[0, 1]`: the axis still has real labels.
 */
export function chartTicks(values: number[], count = 4): number[] {
  const finite = values.filter(Number.isFinite);
  const min = Math.min(0, ...finite);
  const max = Math.max(0, ...finite);
  if (min === 0 && max === 0) return [0, 1];
  const raw = (max - min) / count;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = ([1, 2, 2.5, 5, 10].find((m) => m * power >= raw) ?? 10) * power;
  const first = Math.floor(min / step) * step;
  const last = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = first; v <= last + step / 2; v += step) ticks.push(Math.round(v * 100) / 100);
  return ticks.map((t) => (Object.is(t, -0) ? 0 : t));
}

const axisFormats = new Map<string, Intl.NumberFormat>();

/** A tick label in compact Canadian dollars: `$0`, `$5K`, `$12.5K`, `$1.2M` (fr-CA `5 k $`). */
export function formatAxisMoney(value: number, locale: AppLocale): string {
  const key = intlLocale(locale);
  let format = axisFormats.get(key);
  if (!format) {
    format = new Intl.NumberFormat(key, {
      style: "currency",
      currency: "CAD",
      notation: "compact",
      minimumFractionDigits: 0,
      maximumFractionDigits: 1,
    });
    axisFormats.set(key, format);
  }
  return format.format(Object.is(value, -0) ? 0 : value);
}

// ---- shared frame ------------------------------------------------------------------------------

const WIDTH = 640; // viewBox width; the SVG scales to its container
const LEFT = 56;
const RIGHT = 8;
const TOP = 8;
const BOTTOM = 24;

interface Frame {
  ticks: number[];
  y: (value: number) => number;
  plotWidth: number;
  height: number;
  shown: ChartSeries[];
}

function useFrame(series: ChartSeries[], categories: ChartCategory[], height: number): Frame {
  return useMemo(() => {
    if (series.length > CHART_SERIES.length) {
      console.warn(
        `Charts show at most ${CHART_SERIES.length} series; fold the rest into "Other" or use small multiples.`,
      );
    }
    const shown = series.slice(0, CHART_SERIES.length);
    const values = shown.flatMap((s) => categories.map((_, i) => toNumber(s.values[i])));
    const ticks = chartTicks(values);
    const low = ticks[0] ?? 0;
    const high = ticks.at(-1) ?? 1;
    const plotHeight = height - TOP - BOTTOM;
    const y = (value: number) => TOP + ((high - value) / (high - low || 1)) * plotHeight;
    return { ticks, y, plotWidth: WIDTH - LEFT - RIGHT, height, shown };
  }, [series, categories, height]);
}

function Axis({
  frame,
  categories,
  locale,
  x,
}: {
  frame: Frame;
  categories: ChartCategory[];
  locale: AppLocale;
  x: (index: number) => number;
}) {
  return (
    <g aria-hidden="true" className="text-[11px]" fill="currentColor">
      {frame.ticks.map((tick) => (
        <g key={tick} data-tick={tick}>
          <line
            x1={LEFT}
            x2={WIDTH - RIGHT}
            y1={frame.y(tick)}
            y2={frame.y(tick)}
            stroke={tick === 0 ? "var(--color-neutral-400)" : "var(--color-neutral-100)"}
            strokeWidth={1}
          />
          <text
            x={LEFT - 6}
            y={frame.y(tick)}
            textAnchor="end"
            dominantBaseline="middle"
            className="fill-fg-muted"
          >
            {formatAxisMoney(tick, locale)}
          </text>
        </g>
      ))}
      {categories.map((category, i) => (
        <text
          key={category.key}
          x={x(i)}
          y={frame.height - 6}
          textAnchor="middle"
          className="fill-fg-muted"
        >
          {category.label}
        </text>
      ))}
    </g>
  );
}

function Legend({ series }: { series: ChartSeries[] }) {
  if (series.length < 2) return null;
  return (
    <ul className="flex flex-wrap gap-4 text-xs text-fg-muted" data-chart-legend="">
      {series.map((s, i) => (
        <li key={s.key} className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className="inline-block size-2.5 rounded-sm"
            style={{ background: CHART_SERIES[i] }}
          />
          {s.label}
        </li>
      ))}
    </ul>
  );
}

function ChartTable({
  categories,
  series,
  locale,
  labels,
  id,
}: {
  categories: ChartCategory[];
  series: ChartSeries[];
  locale: AppLocale;
  labels: ChartLabels;
  id: string;
}) {
  return (
    <table id={id} className="w-full text-sm" data-chart-table="">
      <caption className="sr-only">{labels.chart}</caption>
      <thead>
        <tr className="border-b border-border text-xs text-fg-muted">
          <th scope="col" className="py-1 text-start">
            {labels.category}
          </th>
          {series.map((s) => (
            <th key={s.key} scope="col" className="py-1 text-end">
              {s.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {categories.map((category, i) => (
          <tr key={category.key} className="border-b border-border">
            <th scope="row" className="py-1 text-start font-normal">
              {category.label}
            </th>
            {series.map((s) => (
              <td key={s.key} className="py-1 text-end tabular-nums">
                {formatMoney(String(s.values[i] ?? "0"), { locale })}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ChartShell({
  props,
  frame,
  children,
}: {
  props: ChartProps;
  frame: Frame;
  children: ReactNode;
}) {
  const { categories, locale, labels, className } = props;
  const [table, setTable] = useState(false);
  const id = useId();
  return (
    <div className={cn("flex flex-col gap-2", className)} data-chart="">
      {table ? (
        <ChartTable
          id={id}
          categories={categories}
          series={frame.shown}
          locale={locale}
          labels={labels}
        />
      ) : (
        <>
          <svg
            role="img"
            aria-label={labels.chart}
            viewBox={`0 0 ${WIDTH} ${frame.height}`}
            className="h-auto w-full text-fg-muted"
            preserveAspectRatio="xMidYMid meet"
          >
            {children}
          </svg>
          <Legend series={frame.shown} />
        </>
      )}
      <button
        type="button"
        className="self-start text-sm text-fg-link underline"
        aria-controls={table ? id : undefined}
        aria-expanded={table}
        onClick={() => setTable((t) => !t)}
      >
        {table ? labels.showChart : labels.showTable}
      </button>
    </div>
  );
}

function pointTitle(
  labels: ChartLabels,
  series: ChartSeries,
  category: ChartCategory,
  value: Amount | undefined,
  locale: AppLocale,
): string {
  const amount = formatMoney(String(value ?? "0"), { locale });
  return labels.point
    ? labels.point(series.label, category.label, amount)
    : `${series.label}, ${category.label}: ${amount}`;
}

// ---- bar chart ---------------------------------------------------------------------------------

const GAP = 2;
const RADIUS = 4;

/** A bar from the zero line to `top`, rounded only at its data end (4 px). */
export function barPath(x: number, width: number, zero: number, end: number): string {
  const height = Math.abs(zero - end);
  if (height < 0.5) return "";
  const r = Math.min(RADIUS, width / 2, height);
  if (end < zero) {
    // up
    return `M${x},${zero}V${end + r}Q${x},${end} ${x + r},${end}H${x + width - r}Q${x + width},${end} ${x + width},${end + r}V${zero}Z`;
  }
  return `M${x},${zero}V${end - r}Q${x},${end} ${x + r},${end}H${x + width - r}Q${x + width},${end} ${x + width},${end - r}V${zero}Z`;
}

export function BarChart(props: ChartProps) {
  const { categories, series, locale, labels, height = 200 } = props;
  const frame = useFrame(series, categories, height);
  const band = frame.plotWidth / Math.max(categories.length, 1);
  const groups = Math.max(frame.shown.length, 1);
  const barWidth = Math.max(2, Math.min(32, (band * 0.7 - GAP * (groups - 1)) / groups));
  const groupWidth = barWidth * groups + GAP * (groups - 1);
  const center = (i: number) => LEFT + band * i + band / 2;
  const zero = frame.y(0);
  return (
    <ChartShell props={props} frame={frame}>
      <Axis frame={frame} categories={categories} locale={locale} x={center} />
      {frame.shown.map((s, si) => (
        <g key={s.key} fill={CHART_SERIES[si]} data-series={s.key}>
          {categories.map((category, i) => {
            const value = toNumber(s.values[i]);
            const x = center(i) - groupWidth / 2 + si * (barWidth + GAP);
            const d = barPath(x, barWidth, zero, frame.y(value));
            return (
              <g key={category.key} data-bar={`${s.key}:${category.key}`}>
                {/* Hit target: the whole band column, wider than the bar. */}
                <rect
                  x={x - GAP}
                  y={TOP}
                  width={barWidth + GAP * 2}
                  height={height - TOP - BOTTOM}
                  fill="transparent"
                >
                  <title>{pointTitle(labels, s, category, s.values[i], locale)}</title>
                </rect>
                {d ? <path d={d} pointerEvents="none" /> : null}
              </g>
            );
          })}
        </g>
      ))}
    </ChartShell>
  );
}

// ---- line chart --------------------------------------------------------------------------------

export function LineChart(props: ChartProps) {
  const { categories, series, locale, labels, height = 200 } = props;
  const frame = useFrame(series, categories, height);
  const step = categories.length > 1 ? frame.plotWidth / (categories.length - 1) : 0;
  const x = (i: number) => (categories.length > 1 ? LEFT + step * i : LEFT + frame.plotWidth / 2);
  return (
    <ChartShell props={props} frame={frame}>
      <Axis frame={frame} categories={categories} locale={locale} x={x} />
      {frame.shown.map((s, si) => {
        const points = categories.map((_, i) => `${x(i)},${frame.y(toNumber(s.values[i]))}`);
        return (
          <g key={s.key} data-series={s.key}>
            {points.length > 1 ? (
              <polyline
                points={points.join(" ")}
                fill="none"
                stroke={CHART_SERIES[si]}
                strokeWidth={2}
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            ) : null}
            {categories.map((category, i) => (
              <circle
                key={category.key}
                data-point={`${s.key}:${category.key}`}
                cx={x(i)}
                cy={frame.y(toNumber(s.values[i]))}
                r={4}
                fill={CHART_SERIES[si]}
                stroke="var(--color-surface)"
                strokeWidth={2}
              >
                <title>{pointTitle(labels, s, category, s.values[i], locale)}</title>
              </circle>
            ))}
          </g>
        );
      })}
    </ChartShell>
  );
}
