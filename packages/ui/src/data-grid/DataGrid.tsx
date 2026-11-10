"use client";

import * as Popover from "@radix-ui/react-popover";
import {
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type Row,
  type SortingState,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";

import { normaliseForSearch, queryWords } from "../org-switcher/search";
import { Button } from "../primitives/Button";
import { Checkbox } from "../primitives/Checkbox";
import { cn } from "../primitives/cn";
import { Input } from "../primitives/Input";
import { Select } from "../primitives/Select";
import { SearchIcon } from "../shell/icons";
import {
  EMPTY_VIEW,
  ROW_HEIGHT,
  type DataGridColumn,
  type DataGridLabels,
  type Density,
  type GridViewState,
} from "./types";

export type DataGridStatus = "ready" | "loading" | "error";

export interface DataGridProps<T> {
  data: readonly T[];
  columns: DataGridColumn<T>[];
  getRowId: (row: T) => string;
  /** Text naming a row for screen readers (row checkbox), e.g. the organisation name. */
  getRowLabel: (row: T) => string;
  labels: DataGridLabels;
  /** Controlled view (sort, search, filters, columns, density) — pair with `useSavedViews`. */
  view?: GridViewState;
  onViewChange?: (view: GridViewState) => void;
  /** Row selection (checkboxes, Space, Shift+click range) and the bulk bar. */
  selectable?: boolean;
  selectedIds?: ReadonlySet<string>;
  onSelectionChange?: (ids: Set<string>) => void;
  /** Bulk bar actions for the selected rows (shown while rows are selected). */
  bulkActions?: (selected: T[]) => ReactNode;
  /** Open a row: Enter on a focused row, or a click on it. */
  onRowOpen?: (row: T) => void;
  status?: DataGridStatus;
  /** No data at all (first-run CTA) — `EmptyState` (A-10-T12). */
  emptyState?: ReactNode;
  /** Data exists but nothing matches the search/filters. */
  noResultsState?: ReactNode;
  /** Loading failed — `ErrorState` with retry (A-10-T12). */
  errorState?: ReactNode;
  /** Extra controls at the end of the toolbar (saved views menu, export…). */
  toolbar?: ReactNode;
  /** Height of the scrolling body in px (the header stays visible). */
  height?: number;
  className?: string;
}

const CHECKBOX_COLUMN_WIDTH = 48;

const collator = new Intl.Collator("en-CA", { numeric: true, sensitivity: "base" });

/** Numbers numerically, text by collation (accents, case, embedded numbers: "Org 2" < "Org 10"). */
function compareValues(a: unknown, b: unknown): number {
  if (a === b) return 0;
  if (a === null || a === undefined || a === "") return 1;
  if (b === null || b === undefined || b === "") return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return collator.compare(String(a), String(b));
}

function cellText(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

/**
 * Data grid (A-10-T10) — the one grid of every list (gap-01): TanStack Table for sorting and
 * filtering, TanStack Virtual so 10,000 rows scroll at 60 fps (only visible rows render).
 *
 * Search box over searchable columns (accent-insensitive, every word), filter chips per column,
 * column chooser, density (comfortable/compact), sticky header, row selection with a bulk bar,
 * loading / empty / no-results / error states. Keyboard: Tab into the rows, ↑/↓ (PageUp/PageDown,
 * Home/End) move, Space selects, Shift+↑/↓ extends, Enter opens.
 */
export function DataGrid<T>({
  data,
  columns,
  getRowId,
  getRowLabel,
  labels,
  view: controlledView,
  onViewChange,
  selectable = false,
  selectedIds,
  onSelectionChange,
  bulkActions,
  onRowOpen,
  status = "ready",
  emptyState,
  noResultsState,
  errorState,
  toolbar,
  height = 560,
  className,
}: DataGridProps<T>) {
  const [ownView, setOwnView] = useState<GridViewState>(EMPTY_VIEW);
  const view = controlledView ?? ownView;
  const setView = useCallback(
    (next: GridViewState) => {
      if (!controlledView) setOwnView(next);
      onViewChange?.(next);
    },
    [controlledView, onViewChange],
  );

  const [ownSelection, setOwnSelection] = useState<Set<string>>(new Set());
  const selection = selectedIds ?? ownSelection;
  const setSelection = useCallback(
    (next: Set<string>) => {
      if (!selectedIds) setOwnSelection(next);
      onSelectionChange?.(next);
    },
    [selectedIds, onSelectionChange],
  );

  const visibleColumns = columns.filter((column) => !view.hiddenColumns.includes(column.id));

  const tableColumns = useMemo<ColumnDef<T>[]>(
    () =>
      columns.map((column) => ({
        id: column.id,
        accessorFn: (row: T) => column.accessor(row),
        enableSorting: column.sortable ?? false,
        sortingFn: (a: Row<T>, b: Row<T>, id: string) =>
          compareValues(a.getValue(id), b.getValue(id)),
        filterFn: (row: Row<T>, id: string, value: string) => cellText(row.getValue(id)) === value,
      })),
    [columns],
  );

  const searchable = useMemo(
    () => columns.filter((column) => column.searchable ?? true),
    [columns],
  );

  // Stable state objects: TanStack recomputes its row models (and queues internal resets)
  // whenever these change identity, so a new array per render would loop.
  const sorting = view.sorting as SortingState;
  const columnFilters = useMemo(
    () =>
      Object.entries(view.filters)
        .filter(([, value]) => value !== "")
        .map(([id, value]) => ({ id, value })),
    [view.filters],
  );

  const table = useReactTable({
    data: data as T[],
    columns: tableColumns,
    getRowId: (row) => getRowId(row),
    // No pagination or row expansion: never reset them (each reset is a state update).
    autoResetPageIndex: false,
    autoResetExpanded: false,
    state: { sorting, globalFilter: view.search, columnFilters },
    onSortingChange: (updater) => {
      const next = typeof updater === "function" ? updater(view.sorting as SortingState) : updater;
      setView({ ...view, sorting: next.map(({ id, desc }) => ({ id, desc })) });
    },
    globalFilterFn: (row, _columnId, query: string) => {
      const words = queryWords(query);
      if (!words.length) return true;
      const text = normaliseForSearch(
        searchable.map((column) => cellText(column.accessor(row.original))).join(" "),
      );
      return words.every((word) => text.includes(word));
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const rows = table.getRowModel().rows;
  const rowHeight = ROW_HEIGHT[view.density];
  const scroller = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => rowHeight,
    overscan: 12,
    initialRect: { width: 1024, height },
  });
  // (row height comes from estimateSize; re-measure when density changes)
  useEffect(() => {
    virtualizer.measure();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowHeight]);

  // ---- keyboard focus (roving tabindex over rows) -----------------------------------------
  const [activeIndex, setActiveIndex] = useState(0);
  const anchorIndex = useRef<number | null>(null);
  useEffect(() => {
    if (activeIndex > rows.length - 1) setActiveIndex(Math.max(0, rows.length - 1));
  }, [rows.length, activeIndex]);

  const focusRow = (index: number) => {
    const clamped = Math.min(Math.max(index, 0), rows.length - 1);
    setActiveIndex(clamped);
    virtualizer.scrollToIndex(clamped, { align: "auto" });
    const find = () =>
      scroller.current?.querySelector<HTMLElement>(`[data-row-index="${clamped}"]`);
    const rendered = find();
    if (rendered) rendered.focus();
    else requestAnimationFrame(() => find()?.focus()); // row renders after the scroll
  };

  const toggleRow = (id: string, on?: boolean) => {
    const next = new Set(selection);
    if (on ?? !next.has(id)) next.add(id);
    else next.delete(id);
    setSelection(next);
  };

  const selectRange = (from: number, to: number) => {
    const next = new Set(selection);
    const [start, end] = from < to ? [from, to] : [to, from];
    for (let i = start; i <= end; i += 1) {
      const row = rows[i];
      if (row) next.add(row.id);
    }
    setSelection(next);
  };

  const onRowKey = (event: ReactKeyboardEvent<HTMLTableRowElement>, index: number, row: Row<T>) => {
    const page = Math.max(1, Math.floor(height / rowHeight) - 1);
    const moves: Record<string, number> = {
      ArrowDown: index + 1,
      ArrowUp: index - 1,
      PageDown: index + page,
      PageUp: index - page,
      Home: 0,
      End: rows.length - 1,
    };
    if (event.key in moves) {
      event.preventDefault();
      const target = moves[event.key]!;
      if (selectable && event.shiftKey && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
        anchorIndex.current ??= index;
        selectRange(anchorIndex.current, Math.min(Math.max(target, 0), rows.length - 1));
      } else {
        anchorIndex.current = null;
      }
      focusRow(target);
    } else if (event.key === " " && selectable) {
      event.preventDefault();
      anchorIndex.current = index;
      toggleRow(row.id);
    } else if (event.key === "Enter" && onRowOpen) {
      event.preventDefault();
      onRowOpen(row.original);
    }
  };

  const onCheckboxClick = (event: ReactMouseEvent, index: number, row: Row<T>) => {
    if (event.shiftKey && anchorIndex.current !== null) {
      event.preventDefault();
      selectRange(anchorIndex.current, index);
    } else {
      anchorIndex.current = index;
    }
    setActiveIndex(index);
    void row;
  };

  // ---- derived states ------------------------------------------------------------------------
  const selectedRows = useMemo(
    () => (selection.size ? data.filter((row) => selection.has(getRowId(row))) : []),
    [data, selection, getRowId],
  );
  const filteredIds = rows.map((row) => row.id);
  const selectedInView = filteredIds.filter((id) => selection.has(id)).length;
  const allState: boolean | "indeterminate" =
    selectedInView === 0 ? false : selectedInView === filteredIds.length ? true : "indeterminate";
  const filtered = view.search.trim() !== "" || Object.values(view.filters).some(Boolean);

  const colCount = visibleColumns.length + (selectable ? 1 : 0);
  const virtualRows = virtualizer.getVirtualItems();
  const padTop = virtualRows[0]?.start ?? 0;
  const padBottom = virtualizer.getTotalSize() - (virtualRows.at(-1)?.end ?? 0);

  let body: ReactNode;
  if (status === "loading") {
    body = Array.from({ length: 6 }, (_, i) => (
      <tr key={`skeleton-${i}`} aria-hidden="true" style={{ height: rowHeight }}>
        {Array.from({ length: colCount }, (_, c) => (
          <td key={c} className="border-b border-border px-3">
            <span
              className="block h-3 animate-pulse rounded bg-surface-muted"
              style={{ width: `${50 + ((i + c) % 4) * 12}%` }}
            />
          </td>
        ))}
      </tr>
    ));
  } else if (status === "error" || (data.length === 0 ? true : rows.length === 0)) {
    const content =
      status === "error"
        ? errorState
        : data.length === 0
          ? emptyState
          : (noResultsState ?? emptyState);
    body = (
      <tr>
        <td colSpan={colCount} className="p-0">
          <div
            data-grid-state={
              status === "error" ? "error" : data.length === 0 ? "empty" : "no-results"
            }
          >
            {content}
          </div>
        </td>
      </tr>
    );
  } else {
    body = (
      <>
        {padTop > 0 ? (
          <tr aria-hidden="true" style={{ height: padTop }}>
            <td colSpan={colCount} />
          </tr>
        ) : null}
        {virtualRows.map((item) => {
          const row = rows[item.index]!;
          const selected = selection.has(row.id);
          return (
            <tr
              key={row.id}
              data-row-index={item.index}
              aria-rowindex={item.index + 2}
              aria-selected={selectable ? selected : undefined}
              tabIndex={item.index === activeIndex ? 0 : -1}
              onFocus={() => setActiveIndex(item.index)}
              onKeyDown={(event) => onRowKey(event, item.index, row)}
              onClick={(event) => {
                if ((event.target as HTMLElement).closest("button, a, input, [role=checkbox]"))
                  return;
                onRowOpen?.(row.original);
              }}
              style={{ height: rowHeight }}
              className={cn(
                "outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-border-focus",
                selected ? "bg-surface-accent-subtle" : "hover:bg-surface-subtle",
                onRowOpen && "cursor-pointer",
              )}
            >
              {selectable ? (
                <td
                  role="gridcell"
                  className="border-b border-border px-3"
                  onClickCapture={(event) => onCheckboxClick(event, item.index, row)}
                >
                  <Checkbox
                    aria-label={labels.selectRow(getRowLabel(row.original))}
                    checked={selected}
                    tabIndex={-1}
                    onCheckedChange={(checked) => toggleRow(row.id, checked === true)}
                  />
                </td>
              ) : null}
              {visibleColumns.map((column) => (
                <td
                  key={column.id}
                  role="gridcell"
                  className={cn(
                    "truncate border-b border-border px-3 text-sm",
                    column.align === "end" && "text-end tabular-nums",
                  )}
                >
                  {column.cell
                    ? column.cell(row.original)
                    : cellText(column.accessor(row.original))}
                </td>
              ))}
            </tr>
          );
        })}
        {padBottom > 0 ? (
          <tr aria-hidden="true" style={{ height: padBottom }}>
            <td colSpan={colCount} />
          </tr>
        ) : null}
      </>
    );
  }

  const filterColumns = columns.filter((column) => column.filterOptions?.length);

  return (
    <div
      className={cn("flex flex-col rounded-lg border border-border bg-surface", className)}
      data-density={view.density}
    >
      {/* Toolbar: search, filter chips, columns, density */}
      <div className="flex flex-wrap items-center gap-2 border-b border-border p-2">
        <label className="relative min-w-48 flex-1 md:max-w-80">
          <span className="sr-only">{labels.search}</span>
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 start-3 flex items-center text-fg-muted"
          >
            <SearchIcon />
          </span>
          <Input
            type="search"
            value={view.search}
            onChange={(event) => setView({ ...view, search: event.target.value })}
            className="ps-9"
          />
        </label>
        {filterColumns.map((column) => (
          <div key={column.id} className="w-44">
            <Select
              aria-label={column.header}
              value={view.filters[column.id] || "__all__"}
              onValueChange={(value) =>
                setView({
                  ...view,
                  filters: { ...view.filters, [column.id]: value === "__all__" ? "" : value },
                })
              }
              options={[
                { value: "__all__", label: labels.filterChip(column.header, labels.filterAll) },
                ...(column.filterOptions ?? []).map((option) => ({
                  value: option.value,
                  label: labels.filterChip(column.header, option.label),
                })),
              ]}
            />
          </div>
        ))}
        {filtered ? (
          <Button variant="ghost" onClick={() => setView({ ...view, search: "", filters: {} })}>
            {labels.clearFilters}
          </Button>
        ) : null}
        <div className="ms-auto flex flex-wrap items-center gap-2">
          {toolbar}
          <ColumnChooser
            label={labels.columns}
            columns={columns}
            hidden={view.hiddenColumns}
            onChange={(hiddenColumns) => setView({ ...view, hiddenColumns })}
          />
          <DensityToggle
            density={view.density}
            labels={labels}
            onChange={(density) => setView({ ...view, density })}
          />
        </div>
      </div>

      {/* Bulk bar */}
      {selectable && selection.size > 0 ? (
        <div
          data-bulk-bar=""
          className="flex flex-wrap items-center gap-2 border-b border-border bg-surface-inverse px-3 py-2 text-fg-inverse"
        >
          <span className="text-sm font-semibold">{labels.selectedCount(selection.size)}</span>
          <div className="flex flex-wrap gap-2 [&_button]:bg-surface">
            {bulkActions?.(selectedRows)}
          </div>
          <button
            type="button"
            onClick={() => setSelection(new Set())}
            className="ms-auto min-h-touch-target rounded-md px-3 text-sm font-semibold text-fg-inverse-accent underline"
          >
            {labels.clearSelection}
          </button>
        </div>
      ) : null}

      <p role="status" className="sr-only">
        {status === "loading"
          ? labels.loading
          : filtered
            ? labels.resultCount(rows.length, data.length)
            : ""}
      </p>

      <div
        ref={scroller}
        className="relative overflow-auto"
        // No scroll anchoring: the virtualiser positions rows itself (anchoring fights it).
        style={{ height, overflowAnchor: "none" }}
        data-grid-scroller=""
      >
        <table
          role="grid"
          aria-label={labels.grid}
          aria-rowcount={status === "ready" ? rows.length + 1 : undefined}
          aria-multiselectable={selectable || undefined}
          aria-busy={status === "loading" || undefined}
          className="w-full table-fixed border-separate border-spacing-0"
        >
          <colgroup>
            {selectable ? <col style={{ width: CHECKBOX_COLUMN_WIDTH }} /> : null}
            {visibleColumns.map((column) => (
              <col key={column.id} style={column.width ? { width: column.width } : undefined} />
            ))}
          </colgroup>
          <thead>
            <tr aria-rowindex={1}>
              {selectable ? (
                <th
                  scope="col"
                  role="columnheader"
                  className="sticky top-0 z-10 border-b border-border-strong bg-surface-subtle px-3"
                >
                  <Checkbox
                    aria-label={labels.selectAll}
                    checked={allState}
                    disabled={status !== "ready" || rows.length === 0}
                    onCheckedChange={() => {
                      const next = new Set(selection);
                      if (allState === true) filteredIds.forEach((id) => next.delete(id));
                      else filteredIds.forEach((id) => next.add(id));
                      setSelection(next);
                    }}
                  />
                </th>
              ) : null}
              {visibleColumns.map((column) => {
                const sort = view.sorting.find((s) => s.id === column.id);
                const ariaSort = sort
                  ? sort.desc
                    ? "descending"
                    : "ascending"
                  : column.sortable
                    ? "none"
                    : undefined;
                return (
                  <th
                    key={column.id}
                    scope="col"
                    role="columnheader"
                    aria-sort={ariaSort}
                    style={{ height: rowHeight }}
                    className={cn(
                      "sticky top-0 z-10 border-b border-border-strong bg-surface-subtle px-3 text-xs font-bold whitespace-nowrap text-fg",
                      column.align === "end" ? "text-end" : "text-start",
                    )}
                  >
                    {column.sortable ? (
                      <button
                        type="button"
                        onClick={() =>
                          table.getColumn(column.id)?.toggleSorting(sort ? !sort.desc : false)
                        }
                        className={cn(
                          "inline-flex min-h-8 items-center gap-1",
                          column.align === "end" && "flex-row-reverse",
                        )}
                      >
                        {column.header}
                        <span aria-hidden="true" className="text-fg-muted">
                          {sort ? (sort.desc ? "▼" : "▲") : "↕"}
                        </span>
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>{body}</tbody>
        </table>
      </div>
    </div>
  );
}

function ColumnChooser<T>({
  label,
  columns,
  hidden,
  onChange,
}: {
  label: string;
  columns: DataGridColumn<T>[];
  hidden: string[];
  onChange: (hidden: string[]) => void;
}) {
  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <Button>{label}</Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={4}
          aria-label={label}
          className="z-50 w-64 rounded-lg border border-border bg-surface p-2 text-fg shadow-elevation-3"
        >
          <fieldset>
            <legend className="sr-only">{label}</legend>
            {columns.map((column) => (
              <Checkbox
                key={column.id}
                label={column.header}
                checked={!hidden.includes(column.id)}
                disabled={column.hideable === false}
                onCheckedChange={(checked) =>
                  onChange(
                    checked ? hidden.filter((id) => id !== column.id) : [...hidden, column.id],
                  )
                }
              />
            ))}
          </fieldset>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function DensityToggle({
  density,
  labels,
  onChange,
}: {
  density: Density;
  labels: DataGridLabels;
  onChange: (density: Density) => void;
}) {
  return (
    <div
      role="group"
      aria-label={labels.density}
      className="inline-flex rounded-md border border-border-strong p-0.5"
    >
      {(["comfortable", "compact"] as const).map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={density === option}
          onClick={() => onChange(option)}
          className={cn(
            "min-h-10 rounded-sm px-3 text-xs font-semibold",
            density === option
              ? "bg-surface-inverse text-fg-inverse"
              : "text-fg hover:bg-surface-muted",
          )}
        >
          {labels[option]}
        </button>
      ))}
    </div>
  );
}
