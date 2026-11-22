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
  /** The cell's value didn't fit (e.g. a pasted value, D-01-T15): flag it. */
  invalid: boolean;
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
  /** Calculated, not typed (Tax amount, Amount): shown, never edited, not a tab stop. */
  readOnly?: boolean;
}

/** Where a person's column choice is kept (D-01-T13): per user and grid. */
export interface ColumnStore {
  /** The hidden column ids, or null when the person never chose (defaults apply). */
  load: () => string[] | null;
  save: (hidden: string[]) => void;
}

/**
 * Column choice in the browser, keyed per user and grid (`numo9.lines.<user>.<grid>`): it
 * survives sign-out and sign-in on the same device; blocked storage keeps it for the page only.
 */
export function localColumnStore(key: string): ColumnStore {
  return {
    load: () => {
      try {
        const raw = window.localStorage.getItem(key);
        const parsed: unknown = raw ? JSON.parse(raw) : null;
        return Array.isArray(parsed) ? parsed.filter((id) => typeof id === "string") : null;
      } catch {
        return null;
      }
    },
    save: (hidden) => {
      try {
        window.localStorage.setItem(key, JSON.stringify(hidden));
      } catch {
        // Storage blocked or full: the choice lasts for this page.
      }
    },
  };
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
  /** Announced after Ctrl+D (D-01-T11): (line) → "Line 3 duplicated". */
  duplicated?: (line: number) => string;
  /**
   * Note when hidden columns hold values (D-01-T13): (columns) → "Discount is hidden but has
   * values." Without it no note is shown.
   */
  hiddenWithValues?: (columns: string) => string;
  /** Button of that note, e.g. "Show". */
  showHidden?: string;
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
  /**
   * Ctrl+D (D-01-T11): the copy of a line placed under it; default: the same values with
   * `newLine()`'s id. Without `labels.duplicated` the shortcut is off.
   */
  duplicateLine?: (line: DocumentLine, fresh: DocumentLine) => DocumentLine;
  /**
   * After a line is deleted (button or Ctrl+Backspace): show an Undo toast — `restore()` puts the
   * line back where it was (D-01-T11).
   */
  onLineRemoved?: (line: DocumentLine, index: number, restore: () => void) => void;
  /** Keeps the person's column choice (D-01-T13); without it the choice lasts for the page. */
  columnStore?: ColumnStore;
  /**
   * Paste from a spreadsheet (D-01-T15): a paste holding tabs or line breaks into a cell hands
   * the rows (cells split on tabs) to this, with the line and the visible columns from the
   * pasted cell on. Without it the browser pastes into the one cell.
   */
  onPasteRows?: (rows: string[][], line: number, columns: string[]) => void;
  /** Cells to flag as not valid, per line id: column ids (D-01-T15). */
  invalidCells?: Readonly<Record<string, readonly string[]>>;
  /**
   * At ≤ 1024 px each line becomes a card with labelled fields (D-01-T16: tablets and narrow
   * windows). The grid keeps its roles, so screen readers still hear rows and cells.
   */
  stacked?: boolean;
}

/** Spreadsheet clipboard text → rows of cells (tabs, CRLF/LF; a trailing line break ignored). */
export function parseTsv(text: string): string[][] {
  const rows = text.replace(/\r\n?/g, "\n").replace(/\n$/, "").split("\n");
  return rows.map((row) => row.split("\t"));
}

/**
 * LineGrid (A-10-T11): the one document line editor — journals now; invoices, bills, purchase
 * orders and quotes in Phase 1 (D-01, E-02) — so every editor behaves the same (gap-01).
 *
 * Keyboard: Tab moves through cells; ↑/↓ move to the same column on the previous/next line;
 * Enter moves down and, on the last line, adds a line; Alt+Shift+↑/↓ moves the line (also
 * Alt+↑/↓ on the line's drag handle); the drag handle reorders with the mouse. Alt+↓ in a cell
 * opens its list (account) or calendar. Ctrl+D duplicates the line (when `labels.duplicated` is
 * given) and Ctrl+Backspace deletes it — `onLineRemoved` offers Undo (D-01-T11). Money cells accept forgiving amounts and are summed exactly in the
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
  duplicateLine,
  onLineRemoved,
  columnStore,
  onPasteRows,
  invalidCells = {},
  stacked = false,
}: LineGridProps) {
  const baseId = useId();
  const table = useRef<HTMLTableElement>(null);
  const [hidden, setHiddenState] = useState<string[]>(defaultHiddenColumns);
  // The saved choice is read after mounting (the server render has no storage).
  useEffect(() => {
    const saved = columnStore?.load();
    if (saved) setHiddenState(saved.filter((id) => columns.some((c) => c.id === id && c.optional)));
    // Only on mount / store change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [columnStore]);
  const setHidden = (next: string[]) => {
    setHiddenState(next);
    columnStore?.save(next);
  };
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

  const removeLine = (index: number, focusColumn?: string) => {
    const removed = latest.current[index];
    if (!removed || latest.current.length <= minLines) return;
    const next = latest.current.filter((_, i) => i !== index);
    commit(next);
    const target = next[Math.min(index, next.length - 1)];
    if (target) pendingFocus.current = cellId(target.id, focusColumn ?? visible[0]?.id ?? "");
    onLineRemoved?.(removed, index, () => {
      const restored = [...latest.current];
      restored.splice(Math.min(index, restored.length), 0, removed);
      commit(restored);
      pendingFocus.current = cellId(removed.id, focusColumn ?? visible[0]?.id ?? "");
    });
  };

  const duplicate = (index: number, focusColumn: string) => {
    const source = latest.current[index];
    if (!source || !labels.duplicated) return;
    const fresh = newLine();
    const copy = duplicateLine ? duplicateLine(source, fresh) : { ...source, id: fresh.id };
    const next = [...latest.current];
    next.splice(index + 1, 0, copy);
    commit(next);
    setAnnouncement(labels.duplicated(index + 1));
    pendingFocus.current = cellId(copy.id, focusColumn);
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
    const command = event.ctrlKey || event.metaKey;
    if (command && !event.altKey && !event.shiftKey && !readOnly) {
      if (event.key === "d" || event.key === "D") {
        if (labels.duplicated) {
          event.preventDefault();
          duplicate(index, columnId);
        }
        return;
      }
      if (event.key === "Backspace") {
        event.preventDefault();
        removeLine(index, columnId);
        return;
      }
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
      // A value that isn't a decimal (a half-typed cell) doesn't break the totals.
      totals[column.id] = sumDecimals(
        lines.map((line) => {
          const value = (line[column.id] as string | null) ?? null;
          return value !== null && /^-?\d+(\.\d+)?$/.test(value) ? value : null;
        }),
      );
    }
  }
  const hasTotals = visible.some((column) => column.total);
  // Hidden columns that hold values: say so, so nothing is invisible by surprise.
  const hiddenWithValues = columns.filter(
    (column) =>
      hidden.includes(column.id) &&
      lines.some((line) => {
        const value = line[column.id];
        return value !== null && value !== undefined && String(value).trim() !== "";
      }),
  );

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
          role="grid"
          aria-label={labels.grid}
          data-stacked={stacked || undefined}
          className={cn(
            "w-full min-w-[40rem] table-fixed border-separate border-spacing-0 text-sm",
            stacked && "max-[1025px]:block max-[1025px]:min-w-0",
          )}
        >
          <colgroup className={cn(stacked && "max-[1025px]:hidden")}>
            <col style={{ width: 44 }} />
            {visible.map((column) => (
              <col key={column.id} style={column.width ? { width: column.width } : undefined} />
            ))}
            <col style={{ width: 52 }} />
          </colgroup>
          <thead className={cn(stacked && "max-[1025px]:sr-only")}>
            <tr role="row">
              <th
                scope="col"
                role="columnheader"
                className="border-b border-border-strong bg-surface-subtle px-2 py-2 text-xs font-bold"
              >
                <span className="sr-only">#</span>
              </th>
              {visible.map((column) => (
                <th
                  key={column.id}
                  scope="col"
                  role="columnheader"
                  className={cn(
                    "border-b border-border-strong bg-surface-subtle px-2 py-2 text-xs font-bold text-fg",
                    column.kind === "money" ? "text-end" : "text-start",
                  )}
                >
                  {column.header}
                </th>
              ))}
              <th
                scope="col"
                role="columnheader"
                className="border-b border-border-strong bg-surface-subtle"
              >
                <span className="sr-only">{labels.actions}</span>
              </th>
            </tr>
          </thead>
          <tbody className={cn(stacked && "max-[1025px]:block max-[1025px]:space-y-3 max-[1025px]:p-2")}>
            {lines.map((line, index) => (
              <tr
                key={line.id}
                role="row"
                data-line={index + 1}
                onDragOver={(event) => onDragOver(event, index)}
                onDrop={(event) => onDrop(event, index)}
                className={cn(
                  stacked &&
                    "max-[1025px]:grid max-[1025px]:grid-cols-2 max-[1025px]:gap-x-3 max-[1025px]:gap-y-1 max-[1025px]:rounded-lg max-[1025px]:border max-[1025px]:border-border max-[1025px]:p-2 max-md:grid-cols-1",
                  dragging === index && "opacity-50",
                  dropAt === index &&
                    dragging !== null &&
                    dragging !== index &&
                    "outline-2 -outline-offset-2 outline-border-focus",
                )}
              >
                <td
                  role="gridcell"
                  className={cn(
                    "border-b border-border px-1 align-middle",
                    stacked && "max-[1025px]:col-span-full max-[1025px]:border-0",
                  )}
                >
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
                  const invalid = invalidCells[line.id]?.includes(column.id) ?? false;
                  return (
                    <td
                      key={column.id}
                      role="gridcell"
                      data-invalid={invalid || undefined}
                      onPasteCapture={(event) => {
                        if (!onPasteRows || readOnly || column.readOnly) return;
                        const text = event.clipboardData.getData("text/plain");
                        if (!/[\t\n]/.test(text.replace(/\r?\n$/, ""))) return;
                        event.preventDefault();
                        const from = visible.findIndex((c) => c.id === column.id);
                        onPasteRows(
                          parseTsv(text),
                          index,
                          visible.slice(from).map((c) => c.id),
                        );
                      }}
                      className={cn(
                        "border-b border-border p-1 align-top",
                        stacked && "max-[1025px]:block max-[1025px]:border-0",
                        stacked && !column.width && "max-[1025px]:col-span-full",
                        invalid && "bg-surface-danger-subtle",
                      )}
                    >
                      {stacked ? (
                        <span
                          aria-hidden="true"
                          className="hidden px-2 text-xs font-semibold text-fg-muted max-[1025px]:block"
                        >
                          {column.header}
                        </span>
                      ) : null}
                      {column.readOnly ? (
                        <output
                          id={id}
                          aria-label={label}
                          // Calculated per line: the totals announce changes, not every cell.
                          aria-live="off"
                          data-numeric={column.kind === "money" ? "" : undefined}
                          className={cn(
                            "flex min-h-10 items-center px-2 text-sm text-fg-muted",
                            column.kind === "money" && "justify-end tabular-nums",
                          )}
                        >
                          {column.kind === "money" && value !== null && value !== undefined
                            ? formatMoney(String(value), { locale, currency })
                            : String(value ?? "")}
                        </output>
                      ) : column.kind === "custom" && column.render ? (
                        column.render({
                          id,
                          label,
                          value,
                          onChange: (v) => update(index, column.id, v),
                          onKeyDown,
                          line,
                          index,
                          invalid,
                        })
                      ) : column.kind === "money" ? (
                        <MoneyCell
                          id={id}
                          label={label}
                          value={(value as string | null) ?? null}
                          locale={locale}
                          readOnly={readOnly}
                          invalid={invalid}
                          placeholder={column.placeholder}
                          onChange={(v) => update(index, column.id, v)}
                          onKeyDown={onKeyDown}
                        />
                      ) : (
                        <input
                          id={id}
                          aria-label={label}
                          aria-invalid={invalid || undefined}
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
                <td
                  role="gridcell"
                  className={cn(
                    "border-b border-border px-1 align-middle",
                    stacked &&
                      "max-[1025px]:col-span-full max-[1025px]:flex max-[1025px]:justify-end max-[1025px]:border-0",
                  )}
                >
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
            <tfoot className={cn(stacked && "max-[1025px]:block max-[1025px]:px-2")}>
              <tr
                data-totals=""
                role="row"
                className={cn(stacked && "max-[1025px]:flex max-[1025px]:flex-wrap max-[1025px]:justify-end")}
              >
                <th
                  scope="row"
                  role="rowheader"
                  colSpan={1 + visible.findIndex((c) => c.total)}
                  className={cn(
                    "px-2 py-2 text-start text-sm font-semibold",
                    stacked && "max-[1025px]:me-auto",
                  )}
                >
                  {labels.totals}
                </th>
                {visible.slice(visible.findIndex((c) => c.total)).map((column) => (
                  <td
                    key={column.id}
                    role="gridcell"
                    className={cn(
                      "px-3 py-2 text-end text-sm font-semibold tabular-nums",
                      stacked && !column.total && "max-[1025px]:hidden",
                    )}
                  >
                    {stacked && column.total ? (
                      <span
                        aria-hidden="true"
                        className="hidden text-xs font-semibold text-fg-muted max-[1025px]:block"
                      >
                        {column.header}
                      </span>
                    ) : null}
                    {column.total
                      ? formatMoney(totals[column.id] ?? "0", { locale, currency })
                      : null}
                  </td>
                ))}
                <td role="gridcell" className={cn(stacked && "max-[1025px]:hidden")} />
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
        {labels.hiddenWithValues && hiddenWithValues.length ? (
          <p data-hidden-note="" className="flex items-center gap-2 text-sm text-fg-muted">
            {labels.hiddenWithValues(hiddenWithValues.map((column) => column.header).join(", "))}
            {labels.showHidden ? (
              <button
                type="button"
                onClick={() =>
                  setHidden(hidden.filter((id) => !hiddenWithValues.some((c) => c.id === id)))
                }
                className="inline-flex min-h-touch-target items-center rounded-md px-2 font-semibold text-fg-link hover:bg-surface-muted"
              >
                {labels.showHidden}
              </button>
            ) : null}
          </p>
        ) : null}
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
  invalid = false,
  placeholder,
  onChange,
  onKeyDown,
}: {
  id: string;
  label: string;
  value: string | null;
  locale: AppLocale;
  readOnly: boolean;
  invalid?: boolean;
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
      aria-invalid={unreadable || invalid || undefined}
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
