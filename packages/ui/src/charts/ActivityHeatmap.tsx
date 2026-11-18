"use client";

/**
 * Activity heatmap (V-05-T08): one square per day over a period (12 months by default), weeks as
 * columns and weekdays as rows, the colour on a 5-step scale relative to the busiest day — and
 * **never colour alone**: every square carries its number in a tooltip (`<title>`), the legend
 * names the scale, and a toggle shows the same numbers as a table (screen readers, exact values).
 *
 * Pure SVG (no chart library). Days are ISO dates (`YYYY-MM-DD`, calendar days — they never
 * shift with time zones); missing days count 0.
 */
import { useId, useMemo, useState } from "react";

import { cn } from "../primitives/cn";

export interface HeatmapDay {
  date: string;
  count: number;
}

export interface ActivityHeatmapLabels {
  /** Accessible name of the chart, e.g. "Activity, last 12 months: 1,204 changes". */
  chart: string;
  less: string;
  more: string;
  showTable: string;
  showChart: string;
  tableDate: string;
  tableCount: string;
  /** Tooltip / table text of one day, e.g. "3 changes on 2 Nov 2026". */
  day: (count: number, date: string) => string;
  /** A date as shown in the table. */
  date: (date: string) => string;
  /** Table caption when there's no activity. */
  empty: string;
}

export interface ActivityHeatmapProps {
  days: HeatmapDay[];
  /** First and last day shown (ISO). */
  from: string;
  to: string;
  labels: ActivityHeatmapLabels;
  /** Start of the week: 0 Sunday (default), 1 Monday. */
  weekStart?: 0 | 1;
  className?: string;
}

/** Fills of the 5 steps (0, then quarters of the busiest day). */
export const HEATMAP_STEPS = [
  "var(--color-neutral-100)",
  "var(--color-green-50)",
  "var(--color-green-100)",
  "var(--color-green-700)",
  "var(--color-green-800)",
] as const;

const CELL = 12;
const GAP = 2;

function parse(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1));
}

function iso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

/** The step (0–4) of a count, relative to the busiest day. */
export function heatmapStep(count: number, max: number): number {
  if (count <= 0 || max <= 0) return 0;
  return Math.min(4, Math.ceil((count / max) * 4));
}

export function ActivityHeatmap({
  days,
  from,
  to,
  labels,
  weekStart = 0,
  className,
}: ActivityHeatmapProps) {
  const [table, setTable] = useState(false);
  const tableId = useId();
  const { cells, weeks, max } = useMemo(() => {
    const counts = new Map(days.map((day) => [day.date, day.count]));
    const start = parse(from);
    const end = parse(to);
    const offset = (start.getUTCDay() - weekStart + 7) % 7;
    const list: { date: string; count: number; week: number; weekday: number }[] = [];
    let max = 0;
    for (let i = 0, d = new Date(start); d <= end; i += 1, d.setUTCDate(d.getUTCDate() + 1)) {
      const date = iso(d);
      const count = counts.get(date) ?? 0;
      max = Math.max(max, count);
      const position = i + offset;
      list.push({ date, count, week: Math.floor(position / 7), weekday: position % 7 });
    }
    return { cells: list, weeks: (list.at(-1)?.week ?? 0) + 1, max };
  }, [days, from, to, weekStart]);

  const width = weeks * (CELL + GAP);
  const height = 7 * (CELL + GAP);
  const busy = days.filter((day) => day.count > 0);

  return (
    <div className={cn("flex flex-col gap-2", className)} data-heatmap="">
      {table ? (
        <table id={tableId} className="w-full max-w-md text-sm">
          <thead>
            <tr className="border-b border-border text-xs text-fg-muted">
              <th className="py-1 text-start">{labels.tableDate}</th>
              <th className="py-1 text-end">{labels.tableCount}</th>
            </tr>
          </thead>
          <tbody>
            {busy.length ? (
              busy.map((day) => (
                <tr key={day.date} className="border-b border-border">
                  <td className="py-1">{labels.date(day.date)}</td>
                  <td className="py-1 text-end tabular-nums">{day.count}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={2} className="py-2 text-fg-muted">
                  {labels.empty}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      ) : (
        <div className="overflow-x-auto">
          <svg
            role="img"
            aria-label={labels.chart}
            width={width}
            height={height}
            viewBox={`0 0 ${width} ${height}`}
          >
            {cells.map((cell) => (
              <rect
                key={cell.date}
                data-date={cell.date}
                data-count={cell.count}
                x={cell.week * (CELL + GAP)}
                y={cell.weekday * (CELL + GAP)}
                width={CELL}
                height={CELL}
                rx={2}
                fill={HEATMAP_STEPS[heatmapStep(cell.count, max)]}
                stroke="var(--color-border)"
                strokeWidth={0.5}
              >
                <title>{labels.day(cell.count, cell.date)}</title>
              </rect>
            ))}
          </svg>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3 text-xs text-fg-muted">
        {!table ? (
          <span className="flex items-center gap-1" aria-hidden="true">
            {labels.less}
            {HEATMAP_STEPS.map((fill) => (
              <svg key={fill} width={CELL} height={CELL}>
                <rect width={CELL} height={CELL} rx={2} fill={fill} stroke="var(--color-border)" />
              </svg>
            ))}
            {labels.more}
          </span>
        ) : null}
        <button
          type="button"
          className="min-h-touch-target rounded-md px-2 text-sm font-semibold text-fg-link underline"
          aria-pressed={table}
          aria-controls={table ? tableId : undefined}
          onClick={() => setTable((value) => !value)}
        >
          {table ? labels.showChart : labels.showTable}
        </button>
      </div>
    </div>
  );
}
