"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type DragEvent as ReactDragEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";

import { ColumnChooser } from "../data-grid/ColumnChooser";
import { sumDecimals } from "../format/decimal";
import { formatMoney } from "../format/format";
import type { AppLocale } from "../format/locale";
import { parseMoney } from "../format/parse";
import { cn } from "../primitives/cn";
import { IconButton } from "../primitives/IconButton";
import { CloseIcon } from "../shell/icons";

export interface DocumentLine {
  /** Stable id (client-generated for new lines). */
  id: string;
  [field: string]: unknown;
}

export interface LineCellProps {
  /** id of the cell's control (focus target). */
  id: string;
  /** Accessible name of the control: "<column> — line <n>". */
  label: string;
  value: unknown;
  onChange: (value: unknown) => void;
  /** Keyboard navigation for custom controls (↑/↓/Enter/Alt+↑/↓). */
  onKeyDown: (event: ReactKeyboardEvent<HTMLElement>) => void;
  line: DocumentLine;
  index: number;
}

export interface LineColumn {
  id: string;
  header: string;
  /** text: free text · money: amount (decimal string) · custom: `render`. */
  kind: "text" | "money" | "custom";
  render?: (cell: LineCellProps) => ReactNode;
  /** Width in px; default shares the rest. */
  width?: number;
  /** Can be hidden in the column chooser. */
  optional?: boolean;
  /** Sum this money column in the totals footer. */
  total?: boolean;
  placeholder?: string;
}

export interface LineGridLabels {
  /** Accessible name of the table, e.g. "Journal lines". */
  grid: string;
  addLine: string;
  /** e.g. (3) → "Delete line 3". */
  removeLine: (line: number) => string;
  /** e.g. (3) → "Move line 3 (drag, or Alt+↑/↓)". */
  moveLine: (line: number) => string;
  /** e.g. ("Debit", 3) → "Debit, line 3". */
  cell: (column: string, line: number) => string;
  columns: string;
  /** Heading of the delete-line column (screen readers), e.g. "Actions". */
  actions: string;
  totals: string;
  /** Announced after a reorder: (from, to) → "Line 2 moved to position 3". */
  moved: (from: number, to: number) => string;
}

export interface LineGridProps {
  lines: DocumentLine[];
  onChange: (lines: DocumentLine[]) => void;
  columns: LineColumn[];
  /** A blank line (new id). */
  newLine: () => DocumentLine;
  labels: LineGridLabels;
  locale: AppLocale;
  currency?: string;
  /** Lines that always stay (deleting below this count is disabled). */
  minLines?: number;
  /** Optional columns hidden initially (ids). */
  defaultHiddenColumns?: string[];
  /** Extra footer content under the totals row (e.g. the journal balance indicator). */
  footer?: (totals: Record<string, string>) => ReactNode;
  readOnly?: boolean;
  className?: string;
}

/**
 * LineGrid (A-10-T11): the one document line editor — journals now; invoices, bills, purchase
 * orders and quotes in Phase 1 (D-01, E-02) — so every editor behaves the same (gap-01).
 *
 * Keyboard: Tab moves through cells; ↑/↓ move to the same column on the previous/next line;
 * Enter moves down and, on the last line, adds a line; Alt+Shift+↑/↓ moves the line (also
 * Alt+↑/↓ on the line's drag handle); the drag handle reorders with the mouse. Alt+↓ in a cell
 * opens its list (account) or calendar. Money cells accept forgiving amounts and are summed exactly in the
 * totals footer. Optional columns are chosen in the column chooser.
 */
export function LineGrid({
  lines,
  onChange,
  columns,
  newLine,
  labels,
  locale,
  currency = "CAD",
  minLines = 1,
  defaultHiddenColumns = [],
  footer,
  readOnly = false,
  className,
}: LineGridProps) {
  const baseId = useId();
  const table = useRef<HTMLTableElement>(null);
  const [hidden, setHidden] = useState<string[]>(defaultHiddenColumns);
  const [announcement, setAnnouncement] = useState("");
  const [dragging, setDragging] = useState<number | null>(null);
  const [dropAt, setDropAt] = useState<number | null>(null);
  const pendingFocus = useRef<string | null>(null);

  // Latest lines, so several changes in one event (commit a cell, then add a line) all apply.
  const latest = useRef(lines);
  latest.current = lines;
  const commit = (next: DocumentLine[]) => {
    latest.current = next;
    onChange(next);
  };

  const visible = columns.filter((column) => !hidden.includes(column.id));
  const cellId = (lineId: string, columnId: string) => `${baseId}-${lineId}-${columnId}`;

  useEffect(() => {
    if (pendingFocus.current) {
      document.getElementById(pendingFocus.current)?.focus();
      pendingFocus.current = null;
    }
  });

  const update = (index: number, field: string, value: unknown) => {
    commit(latest.current.map((line, i) => (i === index ? { ...line, [field]: value } : line)));
  };

  const addLine = (focusColumn?: string) => {
    const line = newLine();
    commit([...latest.current, line]);
    pendingFocus.current = cellId(line.id, focusColumn ?? visible[0]?.id ?? "");
  };

  const removeLine = (index: number) => {
    const next = latest.current.filter((_, i) => i !== index);
    commit(next);
    const target = next[Math.min(index, next.length - 1)];
    if (target) pendingFocus.current = cellId(target.id, visible[0]?.id ?? "");
  };

  const move = (from: number, to: number, focusColumn?: string) => {
    if (to < 0 || to >= latest.current.length || from === to) return;
    const next = [...latest.current];
    const [line] = next.splice(from, 1);
    next.splice(to, 0, line!);
    commit(next);
    setAnnouncement(labels.moved(from + 1, to + 1));
    if (focusColumn) pendingFocus.current = cellId(line!.id, focusColumn);
  };

  const onCellKey = (event: ReactKeyboardEvent<HTMLElement>, index: number, columnId: string) => {
    // A cell control that is showing its own list (combobox open) keeps the arrow keys.
    if ((event.target as HTMLElement).getAttribute("aria-expanded") === "true") return;
    const focusCell = (row: number) => {
      const line = lines[row];
      if (line) document.getElementById(cellId(line.id, columnId))?.focus();
    };
    if (event.altKey && event.shiftKey && (event.key === "ArrowUp" || event.key === "ArrowDown")) {
      event.preventDefault();
      if (!readOnly) move(index, index + (event.key === "ArrowUp" ? -1 : 1), columnId);
      return;
    }
    // Alt+↓ is left to the cell (opens an account list or a calendar).
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (event.key === "ArrowUp") {
      event.preventDefault();
      focusCell(index - 1);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      focusCell(index + 1);
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (index === latest.current.length - 1) {
        if (!readOnly) addLine(columnId);
      } else focusCell(index + 1);
    }
  };

  const totals: Record<string, string> = {};
  for (const column of columns) {
    if (column.kind === "money" && column.total) {
      totals[column.id] = sumDecimals(
        lines.map((line) => (line[column.id] as string | null) ?? null),
      );
    }
  }
  const hasTotals = visible.some((column) => column.total);

  const onDragOver = (event: ReactDragEvent, index: number) => {
    if (dragging === null) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    setDropAt(index);
  };
  const onDrop = (event: ReactDragEvent, index: number) => {
    event.preventDefault();
    if (dragging !== null) move(dragging, index);
    setDragging(null);
    setDropAt(null);
  };

  return (
    <div className={cn("rounded-lg border border-border bg-surface", className)}>
      <div className="flex items-center justify-end gap-2 border-b border-border p-2">
        <ColumnChooser
          label={labels.columns}
          columns={columns.map((column) => ({
            id: column.id,
            header: column.header,
            hideable: column.optional === true,
          }))}
          hidden={hidden}
          onChange={setHidden}
        />
      </div>
      <div className="overflow-x-auto">
        <table
          ref={table}
          aria-label={labels.grid}
          className="w-full min-w-[40rem] table-fixed border-separate border-spacing-0 text-sm"
        >
          <colgroup>
            <col style={{ width: 44 }} />
            {visible.map((column) => (
              <col key={column.id} style={column.width ? { width: column.width } : undefined} />
            ))}
            <col style={{ width: 52 }} />
          </colgroup>
          <thead>
            <tr>
              <th
                scope="col"
                className="border-b border-border-strong bg-surface-subtle px-2 py-2 text-xs font-bold"
              >
                <span className="sr-only">#</span>
              </th>
              {visible.map((column) => (
                <th
                  key={column.id}
                  scope="col"
                  className={cn(
                    "border-b border-border-strong bg-surface-subtle px-2 py-2 text-xs font-bold text-fg",
                    column.kind === "money" ? "text-end" : "text-start",
                  )}
                >
                  {column.header}
                </th>
              ))}
              <th scope="col" className="border-b border-border-strong bg-surface-subtle">
                <span className="sr-only">{labels.actions}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr
                key={line.id}
                data-line={index + 1}
                onDragOver={(event) => onDragOver(event, index)}
                onDrop={(event) => onDrop(event, index)}
                className={cn(
                  dragging === index && "opacity-50",
                  dropAt === index &&
                    dragging !== null &&
                    dragging !== index &&
                    "outline-2 -outline-offset-2 outline-border-focus",
                )}
              >
                <td className="border-b border-border px-1 align-middle">
                  <button
                    type="button"
                    draggable={!readOnly}
                    disabled={readOnly}
                    aria-label={labels.moveLine(index + 1)}
                    onDragStart={(event) => {
                      setDragging(index);
                      event.dataTransfer.effectAllowed = "move";
                      event.dataTransfer.setData("text/plain", line.id);
                    }}
                    onDragEnd={() => {
                      setDragging(null);
                      setDropAt(null);
                    }}
                    onKeyDown={(event) => {
                      if (
                        (event.altKey || event.shiftKey) &&
                        (event.key === "ArrowUp" || event.key === "ArrowDown")
                      ) {
                        event.preventDefault();
                        const to = index + (event.key === "ArrowUp" ? -1 : 1);
                        move(index, to);
                        requestAnimationFrame(() =>
                          table.current
                            ?.querySelector<HTMLElement>(
                              `tr[data-line="${to + 1}"] button[draggable]`,
                            )
                            ?.focus(),
                        );
                      }
                    }}
                    className="inline-flex h-touch-target w-9 cursor-grab items-center justify-center gap-1 rounded-md text-xs text-fg-muted tabular-nums hover:bg-surface-muted active:cursor-grabbing"
                  >
                    <span aria-hidden="true">⋮⋮</span>
                    <span aria-hidden="true">{index + 1}</span>
                  </button>
                </td>
                {visible.map((column) => {
                  const id = cellId(line.id, column.id);
                  const label = labels.cell(column.header, index + 1);
                  const value = line[column.id];
                  const onKeyDown = (event: ReactKeyboardEvent<HTMLElement>) =>
                    onCellKey(event, index, column.id);
                  return (
                    <td key={column.id} className="border-b border-border p-1 align-top">
                      {column.kind === "custom" && column.render ? (
                        column.render({
                          id,
                          label,
                          value,
                          onChange: (v) => update(index, column.id, v),
                          onKeyDown,
                          line,
                          index,
                        })
                      ) : column.kind === "money" ? (
                        <MoneyCell
                          id={id}
                          label={label}
                          value={(value as string | null) ?? null}
                          locale={locale}
                          readOnly={readOnly}
                          placeholder={column.placeholder}
                          onChange={(v) => update(index, column.id, v)}
                          onKeyDown={onKeyDown}
                        />
                      ) : (
                        <input
                          id={id}
                          aria-label={label}
                          value={(value as string | undefined) ?? ""}
                          readOnly={readOnly}
                          placeholder={column.placeholder}
                          onChange={(event) => update(index, column.id, event.target.value)}
                          onKeyDown={onKeyDown}
                          className={CELL_INPUT}
                        />
                      )}
                    </td>
                  );
                })}
                <td className="border-b border-border px-1 align-middle">
                  {readOnly ? null : (
                    <IconButton
                      label={labels.removeLine(index + 1)}
                      icon={<CloseIcon />}
                      size="sm"
                      tooltip={false}
                      disabled={lines.length <= minLines}
                      onClick={() => removeLine(index)}
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
          {hasTotals ? (
            <tfoot>
              <tr data-totals="">
                <th
                  scope="row"
                  colSpan={1 + visible.findIndex((c) => c.total)}
                  className="px-2 py-2 text-start text-sm font-semibold"
                >
                  {labels.totals}
                </th>
                {visible.slice(visible.findIndex((c) => c.total)).map((column) => (
                  <td
                    key={column.id}
                    className="px-3 py-2 text-end text-sm font-semibold tabular-nums"
                  >
                    {column.total
                      ? formatMoney(totals[column.id] ?? "0", { locale, currency })
                      : null}
                  </td>
                ))}
                <td />
              </tr>
            </tfoot>
          ) : null}
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-3 p-2">
        {readOnly ? null : (
          <button
            type="button"
            onClick={() => addLine()}
            className="inline-flex min-h-touch-target items-center rounded-md px-3 text-sm font-semibold text-fg-link hover:bg-surface-muted"
          >
            {labels.addLine}
          </button>
        )}
        {footer ? <div className="ms-auto">{footer(totals)}</div> : null}
      </div>
      <p role="status" className="sr-only">
        {announcement}
      </p>
    </div>
  );
}

const CELL_INPUT =
  "min-h-10 w-full rounded-sm border border-transparent bg-transparent px-2 text-sm text-fg " +
  "hover:border-border focus:border-border-strong focus:bg-surface read-only:hover:border-transparent";

function MoneyCell({
  id,
  label,
  value,
  locale,
  readOnly,
  placeholder,
  onChange,
  onKeyDown,
}: {
  id: string;
  label: string;
  value: string | null;
  locale: AppLocale;
  readOnly: boolean;
  placeholder?: string;
  onChange: (value: string | null) => void;
  onKeyDown: (event: ReactKeyboardEvent<HTMLElement>) => void;
}) {
  const show = (v: string | null) =>
    v === null
      ? ""
      : new Intl.NumberFormat(locale === "fr-CA" ? "fr-CA" : "en-CA", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }).format(v as unknown as number);
  const [text, setText] = useState(show(value));
  const [unreadable, setUnreadable] = useState(false);
  useEffect(() => {
    setText(show(value));
    setUnreadable(false);
    // show() depends only on locale
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, locale]);

  const commit = () => {
    if (!text.trim()) {
      setUnreadable(false);
      if (value !== null) onChange(null);
      return;
    }
    const parsed = parseMoney(text, { locale });
    if (parsed === null) setUnreadable(true);
    else {
      setUnreadable(false);
      if (parsed === value) setText(show(value));
      else onChange(parsed);
    }
  };

  return (
    <input
      id={id}
      aria-label={label}
      aria-invalid={unreadable || undefined}
      inputMode="decimal"
      autoComplete="off"
      readOnly={readOnly}
      placeholder={placeholder}
      value={text}
      onChange={(event) => setText(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") commit();
        onKeyDown(event);
      }}
      data-numeric=""
      className={cn(CELL_INPUT, "text-end tabular-nums", unreadable && "border-border-danger")}
    />
  );
}
