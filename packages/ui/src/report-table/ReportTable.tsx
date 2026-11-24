"use client";

/**
 * Report table (K-01-T13): the results grid of every report — a sticky header row and a sticky
 * first column (the row labels), sections, plain rows, totals and text blocks, a ⤢ drill button on
 * every figure a row can drill into, a compact density, and **windowed rendering** for long
 * reports (only the rows in view, plus a margin, are in the DOM; the scroll height is kept by
 * spacer rows). Wide reports (12 comparison columns) scroll inside the table, never the page.
 *
 * The table never prints "–": an empty cell is empty (K-01-T16 adds the no-activity rules).
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { formatMoney, type AppLocale } from "../format";
import { cn } from "../primitives/cn";

export type ReportRowKind = "section" | "row" | "total" | "text";

export interface ReportTableColumn {
  key: string;
  label: string;
}

export interface ReportTableRow {
  key: string;
  label: string;
  kind: ReportRowKind;
  level?: number;
  /** Decimal strings, one per column; `null` = empty cell. */
  values: (string | null)[];
  /** The row can drill into its figures (K-01-T05). */
  drillable?: boolean;
  /** Cell notes by column key ("" = the whole row), shown as a marker with the text. */
  notes?: Record<string, string>;
}

export interface ReportTableLabels {
  /** Accessible name of a drill button: "Show the lines of {row}, {column}". */
  drill: (row: string, column: string) => string;
  /** Prefix read before a cell note. */
  note: string;
}

export interface ReportTableProps {
  caption: string;
  columns: ReportTableColumn[];
  rows: ReportTableRow[];
  locale: AppLocale;
  labels: ReportTableLabels;
  onDrill?: (row: ReportTableRow, column: number) => void;
  compact?: boolean;
  /** Negative figures in parentheses (financial statements). */
  accounting?: boolean;
  /** Rows above this count are windowed. */
  windowAbove?: number;
  /** Height of the scrolling area when windowed (px). */
  maxHeight?: number;
  className?: string;
  /** Rendered under the table (footnotes). */
  footer?: ReactNode;
}

export const WINDOW_ABOVE = 200;
const ROW_HEIGHT = { comfortable: 40, compact: 30 } as const;
const OVERSCAN = 20;

function DrillIcon() {
  return (
    <svg viewBox="0 0 16 16" className="size-3.5" aria-hidden="true">
      <path
        d="M9.5 2.5h4v4M13.5 2.5 8.5 7.5M6.5 13.5h-4v-4M2.5 13.5l5-5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** The rows to render for a scroll position: `[first, last)` with overscan. */
export function visibleWindow(
  count: number,
  scrollTop: number,
  viewport: number,
  rowHeight: number,
  overscan = OVERSCAN,
): [number, number] {
  const first = Math.min(count, Math.max(0, Math.floor(scrollTop / rowHeight) - overscan));
  const last = Math.min(count, Math.ceil((scrollTop + viewport) / rowHeight) + overscan);
  return [first, Math.max(first, last)];
}

export function ReportTable({
  caption,
  columns,
  rows,
  locale,
  labels,
  onDrill,
  compact = false,
  accounting = false,
  windowAbove = WINDOW_ABOVE,
  maxHeight = 640,
  className,
  footer,
}: ReportTableProps) {
  const scroller = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const windowed = rows.length > windowAbove;
  const rowHeight = compact ? ROW_HEIGHT.compact : ROW_HEIGHT.comfortable;
  const [first, last] = useMemo(
    () =>
      windowed ? visibleWindow(rows.length, scrollTop, maxHeight, rowHeight) : [0, rows.length],
    [windowed, rows.length, scrollTop, maxHeight, rowHeight],
  );
  const onScroll = useCallback(() => {
    if (windowed && scroller.current) setScrollTop(scroller.current.scrollTop);
  }, [windowed]);
  useEffect(() => {
    if (!windowed) setScrollTop(0);
  }, [windowed]);

  const money = (value: string) => formatMoney(value, { locale, accounting });
  const cell = compact ? "px-3 py-1" : "px-3 py-2";
  const shown = rows.slice(first, last);

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div
        ref={scroller}
        onScroll={onScroll}
        className="relative max-w-full overflow-auto rounded-lg border border-border bg-surface"
        style={windowed ? { maxHeight } : undefined}
        data-report-table=""
        data-windowed={windowed ? "" : undefined}
        tabIndex={0}
        role="region"
        aria-label={caption}
      >
        <table className="w-full border-separate border-spacing-0 text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              <th
                scope="col"
                className={cn(
                  "sticky start-0 top-0 z-20 min-w-56 border-b border-border bg-surface-muted text-start font-semibold text-fg",
                  cell,
                )}
              >
                <span className="sr-only">{caption}</span>
              </th>
              {columns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  className={cn(
                    "sticky top-0 z-10 min-w-32 whitespace-nowrap border-b border-border bg-surface-muted text-end font-semibold text-fg",
                    cell,
                  )}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {first > 0 ? (
              <tr aria-hidden="true" style={{ height: first * rowHeight }} data-spacer="" />
            ) : null}
            {shown.map((row) => {
              const strong = row.kind === "section" || row.kind === "total";
              const rowNote = row.notes?.[""];
              return (
                <tr
                  key={row.key}
                  data-row={row.key}
                  data-kind={row.kind}
                  className={cn("group", row.kind === "total" && "bg-surface-muted/60")}
                  style={windowed ? { height: rowHeight } : undefined}
                >
                  <th
                    scope="row"
                    colSpan={row.kind === "text" ? columns.length + 1 : undefined}
                    className={cn(
                      "sticky start-0 z-[5] border-b border-border bg-surface text-start font-normal text-fg",
                      cell,
                      strong && "font-semibold",
                      row.kind === "total" && "border-t border-t-border-strong bg-surface-muted",
                      row.kind === "text" && "whitespace-pre-line italic text-fg-muted",
                    )}
                    style={{ paddingInlineStart: `${0.75 + (row.level ?? 0) * 1.25}rem` }}
                  >
                    {row.label}
                    {rowNote ? (
                      <span className="ms-2 text-xs text-fg-muted" data-note="">
                        <span className="sr-only">{labels.note} </span>
                        {rowNote}
                      </span>
                    ) : null}
                  </th>
                  {row.kind === "text"
                    ? null
                    : columns.map((column, index) => {
                        const value = row.values[index] ?? null;
                        const note = row.notes?.[column.key];
                        return (
                          <td
                            key={column.key}
                            className={cn(
                              "whitespace-nowrap border-b border-border text-end tabular-nums text-fg",
                              cell,
                              strong && "font-semibold",
                              row.kind === "total" && "border-t border-t-border-strong",
                            )}
                            data-column={column.key}
                          >
                            <span className="inline-flex items-center justify-end gap-1">
                              {value !== null && row.drillable && onDrill ? (
                                <button
                                  type="button"
                                  className="inline-flex size-6 items-center justify-center rounded text-fg-muted opacity-0 hover:bg-surface-muted focus-visible:opacity-100 group-hover:opacity-100"
                                  aria-label={labels.drill(row.label, column.label)}
                                  onClick={() => onDrill(row, index)}
                                >
                                  <DrillIcon />
                                </button>
                              ) : null}
                              {value === null ? null : <span>{money(value)}</span>}
                            </span>
                            {note ? (
                              <span
                                className="block text-xs font-normal text-fg-muted"
                                data-note=""
                              >
                                <span className="sr-only">{labels.note} </span>
                                {note}
                              </span>
                            ) : null}
                          </td>
                        );
                      })}
                </tr>
              );
            })}
            {last < rows.length ? (
              <tr
                aria-hidden="true"
                style={{ height: (rows.length - last) * rowHeight }}
                data-spacer=""
              />
            ) : null}
          </tbody>
        </table>
      </div>
      {footer}
    </div>
  );
}
