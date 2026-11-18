"use client";

import {
  Button,
  CloseIcon,
  DataGrid,
  Dialog,
  EmptyState,
  ErrorState,
  Input,
  type DataGridLabels,
  type GridViewState,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";

import { apiRequest } from "@/auth/client";
import type { BulkJob } from "@/bulk/api";
import { BulkActionDialog } from "@/bulk/BulkActionDialog";
import { BulkProgressDrawer } from "@/bulk/BulkProgressDrawer";
import { SelectionBar, type BulkActionKey } from "@/bulk/SelectionBar";
import { EMPTY_SELECTION, type BulkSelection } from "@/bulk/selection";
import { useFormatMessage, type FormatMessage } from "@/i18n";
import { orgModuleUrl, practiceGroupsUrl } from "@/routing/routes";

import {
  directoryApi,
  FILTER_KEYS,
  sameState,
  stateToView,
  viewToState,
  type DirectoryPage,
  type DirectoryRow,
  type DirectoryState,
  type FacetValue,
  type FilterKey,
  type SavedView,
} from "./api";
import { ACTIONS_COLUMN, ALL_COLUMNS, DEFAULT_COLUMNS, directoryColumns } from "./columns";
import { FACET_TITLES, FiltersPanel } from "./FiltersPanel";
import { GroupedDirectory } from "./GroupedDirectory";
import { m } from "./messages";
import { SavedViewsRail } from "./SavedViewsRail";
import { SEARCH_DEBOUNCE_MS, useDebounced } from "./useDebounced";

export { SEARCH_DEBOUNCE_MS };

export const DEFAULT_STATE: DirectoryState = {
  q: "",
  filters: {},
  archived: false,
  sort: [],
  columns: DEFAULT_COLUMNS,
  density: "comfortable",
};

export function useGridLabels(t: FormatMessage): DataGridLabels {
  return useMemo(
    () => ({
      grid: t(m.gridName),
      search: t(m.gridSearch),
      columns: t(m.gridColumns),
      density: t(m.gridDensity),
      comfortable: t(m.gridComfortable),
      compact: t(m.gridCompact),
      filterAll: t(m.gridAll),
      filterChip: (column, value) => t(m.gridChip, { column, value }),
      clearFilters: t(m.gridClear),
      selectAll: t(m.gridSelectAll),
      selectRow: (row) => t(m.gridSelectRow, { row }),
      selectedCount: (count) => t(m.gridSelected, { count }),
      clearSelection: t(m.gridClearSelection),
      resultCount: (shown, total) => t(m.gridResults, { shown, total }),
      loading: t(m.loading),
      reorderHint: t(m.gridReorder),
      columnMoved: (column, position, total) => t(m.gridMoved, { column, position, total }),
    }),
    [t],
  );
}

/** Directory state ↔ the grid's view (sort, search, shown columns in order, density). */
function toView(state: DirectoryState): GridViewState {
  const hidden = ALL_COLUMNS.filter((id) => !state.columns.includes(id));
  return {
    sorting: state.sort.map((key) => ({ id: key.replace(/^-/, ""), desc: key.startsWith("-") })),
    search: state.q,
    filters: {},
    hiddenColumns: hidden,
    density: state.density,
    columnOrder: [...state.columns, ...hidden, ACTIONS_COLUMN],
  };
}

function fromView(view: GridViewState, state: DirectoryState): DirectoryState {
  const order = view.columnOrder ?? [...ALL_COLUMNS];
  return {
    ...state,
    q: view.search,
    sort: view.sorting.map((s) => (s.desc ? `-${s.id}` : s.id)),
    columns: order.filter(
      (id) =>
        id !== ACTIONS_COLUMN &&
        !view.hiddenColumns.includes(id) &&
        ALL_COLUMNS.includes(id as never),
    ),
    density: view.density,
  };
}

function isFiltered(state: DirectoryState): boolean {
  return (
    state.q.trim() !== "" || state.archived || FILTER_KEYS.some((k) => state.filters[k]?.length)
  );
}

function typing(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (!element) return false;
  return (
    element.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName) ||
    element.getAttribute("role") === "combobox"
  );
}

export interface DirectoryScreenProps {
  /** A bulk action chosen in the selection bar (V-03): the selection as the API takes it. */
  onBulkAction?: (action: BulkActionKey, selection: BulkSelection) => void;
  /** Practice public id (`/p/:practice/directory`). */
  practice: string;
  /** Navigation (Next.js `router.push`); defaults to `window.location.assign`. */
  navigate?: (href: string) => void;
  /** Opening a new tab (default `window.open(href, "_blank", "noopener")`). */
  openTab?: (href: string) => void;
  /** U-07 demo organisation; "Open demo" is offered only when it exists. */
  demoHref?: string;
}

/**
 * Organisation directory (V-01-T09…T15) — the accountant's home: every organisation of the
 * practice the user may open, from `GET /api/v1/practice/orgs`.
 *
 * - Virtualised DataGrid in server mode (2,000 rows, sticky header, status chips, row actions);
 * - search box (`/` focuses it) asking the server 150 ms after the last key, matches highlighted;
 * - filters panel (`F`) with the server's facet counts, active filters as removable chips;
 * - column chooser with reorder, density, saved views rail (server-stored, per user);
 * - keyboard: `↓` from search into the rows, `↑/↓` move, `Enter` opens, `Ctrl/⌘+Enter` new tab;
 * - first-run empty, no-results, loading skeleton and error-with-retry states.
 */
export function DirectoryScreen({
  practice,
  navigate,
  openTab,
  demoHref,
  onBulkAction,
}: DirectoryScreenProps) {
  const t = useFormatMessage();
  const locale = useLocale();
  const labels = useGridLabels(t);
  const [state, setState] = useState<DirectoryState>(DEFAULT_STATE);
  const [page, setPage] = useState<DirectoryPage | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [attempt, setAttempt] = useState(0);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [views, setViews] = useState<SavedView[]>([]);
  const [viewsFailed, setViewsFailed] = useState(false);
  const [viewsLoaded, setViewsLoaded] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const [height, setHeight] = useState(560);
  const [groupBy, setGroupBy] = useState<"" | "group">("");
  // V-03-T08: ticked rows, or every organisation matching (the server's query).
  const [selection, setSelection] = useState<BulkSelection>(EMPTY_SELECTION);
  // V-03-T09/T10: the bulk action being prepared, then the job it started.
  const [bulk, setBulk] = useState<{ action: BulkActionKey; selection: BulkSelection } | null>(
    null,
  );
  const [bulkJob, setBulkJob] = useState<BulkJob | null>(null);
  const groupById = useId();
  const gridBox = useRef<HTMLDivElement>(null);

  const go = useCallback(
    (href: string) => (navigate ? navigate(href) : window.location.assign(href)),
    [navigate],
  );
  const goNewTab = useCallback(
    (href: string) => (openTab ? openTab(href) : window.open(href, "_blank", "noopener")),
    [openTab],
  );

  // ---- saved views: load once, open the default view first ---------------------------------
  useEffect(() => {
    let cancelled = false;
    void directoryApi.views(practice).then((result) => {
      if (cancelled) return;
      if (result.status === 200 && Array.isArray(result.body)) {
        setViews(result.body);
        const preferred = result.body.find((view) => view.is_default);
        if (preferred) {
          setActiveId(preferred.id);
          setState(viewToState(preferred, DEFAULT_COLUMNS));
        }
      } else {
        setViewsFailed(true);
      }
      setViewsLoaded(true);
    });
    return () => {
      cancelled = true;
    };
  }, [practice]);

  // ---- the directory request (search debounced; filters, sort and columns at once) ---------
  const q = useDebounced(state.q, SEARCH_DEBOUNCE_MS);
  const requestKey = JSON.stringify([q, state.filters, state.archived, state.sort, state.columns]);
  const request = useMemo(() => {
    const [query, filters, archived, sort, shown] = JSON.parse(requestKey) as [
      string,
      DirectoryState["filters"],
      boolean,
      string[],
      string[],
    ];
    return { q: query, filters, archived, sort, columns: shown };
  }, [requestKey]);
  // "All matching" belongs to the search and filters it was made from: a new query clears it.
  useEffect(() => {
    setSelection((current) => (current.mode === "all" ? EMPTY_SELECTION : current));
  }, [requestKey]);
  useEffect(() => {
    if (!viewsLoaded) return; // the default view decides the first request
    const controller = new AbortController();
    void directoryApi
      .list({ practice, ...request, groupBy, signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (result.status === 200 && Array.isArray(result.body.results)) {
          setPage(result.body);
          setStatus("ready");
        } else {
          setStatus("error");
        }
      });
    return () => controller.abort();
  }, [practice, request, attempt, viewsLoaded, groupBy]);

  // ---- grid height: the rest of the window -----------------------------------------------
  useEffect(() => {
    const fit = () => {
      const top = gridBox.current?.getBoundingClientRect().top ?? 240;
      setHeight(Math.max(320, Math.round(window.innerHeight - top - 24)));
    };
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [filtersOpen]);

  // ---- keyboard: "/" search, "F" filters -------------------------------------------------
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
      if (typing(event.target) || document.querySelector("[role=dialog]")) return;
      if (event.key === "/") {
        event.preventDefault();
        document.querySelector<HTMLInputElement>("[data-directory] [data-grid-search]")?.focus();
      } else if (event.key === "f" || event.key === "F") {
        event.preventDefault();
        setFiltersOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const facetLabel = useCallback(
    (filter: string, value: string) =>
      page?.facets?.[filter as FilterKey]?.find((item) => item.value === value)?.label ?? value,
    [page],
  );
  const columns = useMemo(
    () => directoryColumns({ t, locale, query: q, labels: facetLabel }),
    [t, locale, q, facetLabel],
  );

  const active = views.find((view) => view.id === activeId) ?? null;
  const baseline = active ? viewToState(active, DEFAULT_COLUMNS) : DEFAULT_STATE;
  const modified = !sameState(state, baseline);
  const filtered = isFiltered(state);
  const filterCount = FILTER_KEYS.reduce((n, k) => n + (state.filters[k]?.length ?? 0), 0);

  const toggle = (filter: FilterKey, value: string, on: boolean) =>
    setState((current) => {
      const values = current.filters[filter] ?? [];
      const next = on ? [...values, value] : values.filter((v) => v !== value);
      return { ...current, filters: { ...current.filters, [filter]: next } };
    });

  // ---- saved views actions ---------------------------------------------------------------
  const problem = (result: { status: number; body: unknown }): string => {
    const detail = (result.body as { detail?: unknown } | null)?.detail;
    return result.status === 400 && typeof detail === "string" ? detail : t(m.viewsFailed);
  };
  const saveView = async (name: string): Promise<string | null> => {
    const result = await directoryApi.createView({ practice, name, ...stateToView(state) });
    if (result.status !== 201) return problem(result);
    setViews((current) => [...current, result.body].sort((a, b) => a.name.localeCompare(b.name)));
    setActiveId(result.body.id);
    setAnnouncement(t(m.viewSaved, { name: result.body.name }));
    return null;
  };
  const updateView = async (view: SavedView) => {
    const result = await directoryApi.updateView(view.id, stateToView(state));
    if (result.status === 200) {
      setViews((current) => current.map((v) => (v.id === view.id ? result.body : v)));
      setAnnouncement(t(m.viewSaved, { name: result.body.name }));
    }
  };
  const renameView = async (view: SavedView, name: string): Promise<string | null> => {
    const result = await directoryApi.updateView(view.id, { name });
    if (result.status !== 200) return problem(result);
    setViews((current) => current.map((v) => (v.id === view.id ? result.body : v)));
    return null;
  };
  const setDefault = async (view: SavedView) => {
    const result = await directoryApi.updateView(view.id, { is_default: true });
    if (result.status === 200) {
      setViews((current) =>
        current.map((v) => (v.id === view.id ? result.body : { ...v, is_default: false })),
      );
    }
  };
  const deleteView = async (view: SavedView) => {
    const result = await directoryApi.deleteView(view.id);
    if (result.status === 204) {
      setViews((current) => current.filter((v) => v.id !== view.id));
      if (activeId === view.id) setActiveId(null);
      setAnnouncement(t(m.viewDeleted, { name: view.name }));
    }
  };

  const view = useMemo(() => toView(state), [state]);
  const rows: DirectoryRow[] = page?.results ?? [];
  const selectedIds = useMemo(
    () =>
      selection.mode === "all"
        ? new Set((page?.results ?? []).map((row) => row.id))
        : selection.ids,
    [selection, page],
  );
  const total = page?.total ?? 0;
  const chips = FILTER_KEYS.flatMap((key) =>
    (state.filters[key] ?? []).map((value) => ({ key, value })),
  );

  return (
    <div data-directory="" className="flex flex-col gap-4 md:flex-row">
      <SavedViewsRail
        views={views}
        activeId={activeId}
        modified={modified}
        failed={viewsFailed}
        onApplyAll={() => {
          setActiveId(null);
          setState(DEFAULT_STATE);
        }}
        onApply={(view) => {
          setActiveId(view.id);
          setState(viewToState(view, DEFAULT_COLUMNS));
        }}
        onSave={saveView}
        onUpdate={(view) => void updateView(view)}
        onRename={renameView}
        onSetDefault={(view) => void setDefault(view)}
        onDelete={(view) => void deleteView(view)}
      />

      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-fg">{t(m.title)}</h1>
            <p className="min-h-5 text-sm text-fg-muted" data-directory-summary="">
              {status !== "ready" || !page
                ? null
                : filtered
                  ? t(m.summaryFiltered, { count: page.count, total })
                  : t(m.summary, { total, practice: page.practice.name })}
              {active ? (
                <span className="ms-3 font-semibold">
                  {t(modified ? m.viewChanged : m.viewOpen, { name: active.name })}
                </span>
              ) : null}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {active && modified ? (
              <Button onClick={() => void updateView(active)}>{t(m.viewsSaveChanges)}</Button>
            ) : null}
            <a
              href={practiceGroupsUrl(practice)}
              className="inline-flex min-h-touch-target items-center px-2 text-sm font-semibold text-fg underline"
            >
              {t(m.manageGroups)}
            </a>
            <Button variant="primary" onClick={() => setCreating(true)}>
              {t(m.newOrganisation)}
            </Button>
          </div>
        </header>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            aria-expanded={filtersOpen}
            aria-keyshortcuts="F"
            onClick={() => setFiltersOpen((open) => !open)}
          >
            {filterCount ? t(m.filtersCount, { count: filterCount }) : t(m.filters)}
          </Button>
          <div
            role="group"
            aria-labelledby={groupById}
            className="flex items-center gap-1"
            data-group-by=""
          >
            <span id={groupById} className="me-1 text-sm font-medium text-fg">
              {t(m.groupBy)}
            </span>
            {(["", "group"] as const).map((value) => (
              <Button
                key={value || "none"}
                size="sm"
                variant={groupBy === value ? "primary" : "secondary"}
                aria-pressed={groupBy === value}
                onClick={() => setGroupBy(value)}
              >
                {t(value ? m.groupByGroup : m.groupByNone)}
              </Button>
            ))}
          </div>
          <ul className="flex flex-wrap gap-2" data-filter-chips="">
            {chips.map(({ key, value }) => {
              const chip = t(m.gridChip, {
                column: t(FACET_TITLES[key]),
                value: facetLabel(key, value),
              });
              return (
                <li key={`${key}:${value}`}>
                  <button
                    type="button"
                    aria-label={t(m.removeFilter, { chip })}
                    onClick={() => toggle(key, value, false)}
                    className="min-h-8 rounded-full border border-border-strong bg-surface-accent-subtle px-3 text-xs font-semibold text-fg"
                  >
                    <span className="inline-flex items-center gap-1">
                      {chip}
                      <span aria-hidden="true" className="inline-flex size-4">
                        <CloseIcon />
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="flex flex-col gap-3 md:flex-row">
          {filtersOpen ? (
            <FiltersPanel
              facets={(page?.facets ?? {}) as Partial<Record<FilterKey, FacetValue[]>>}
              state={state}
              onToggle={toggle}
              onArchived={(archived) => setState((current) => ({ ...current, archived }))}
              onClose={() => setFiltersOpen(false)}
            />
          ) : null}
          <div ref={gridBox} className="min-w-0 flex-1">
            {groupBy === "group" && status === "ready" && page?.grouping && rows.length ? (
              <GroupedDirectory
                grouping={page.grouping}
                rows={rows}
                columns={columns}
                labels={labels}
                view={view}
                onViewChange={(view) => setState((current) => fromView(view, current))}
                onRowOpen={(row) => go(orgModuleUrl(row.id, "home"))}
                onRowOpenNewTab={(row) => goNewTab(orgModuleUrl(row.id, "home"))}
              />
            ) : (
              <DataGrid
                manual
                selectable
                selectedIds={selectedIds}
                onSelectionChange={(ids) => setSelection({ mode: "ids", ids })}
                bulkActions={() => (
                  <SelectionBar
                    selection={selection}
                    matching={page?.count ?? rows.length}
                    onSelectAll={() =>
                      setSelection({
                        mode: "all",
                        query: { q: state.q, filters: state.filters, archived: state.archived },
                        count: page?.count ?? rows.length,
                      })
                    }
                    onAction={(action) =>
                      onBulkAction
                        ? onBulkAction(action, selection)
                        : setBulk({ action, selection })
                    }
                  />
                )}
                data={rows}
                columns={columns}
                getRowId={(row) => row.id}
                getRowLabel={(row) => row.name}
                labels={labels}
                view={view}
                onViewChange={(view) => setState((current) => fromView(view, current))}
                onRowOpen={(row) => go(orgModuleUrl(row.id, "home"))}
                onRowOpenNewTab={(row) => goNewTab(orgModuleUrl(row.id, "home"))}
                totalCount={page?.count}
                unfilteredCount={total}
                isFiltered={filtered}
                searchPlaceholder={t(m.searchPlaceholder)}
                status={status}
                height={height}
                emptyState={
                  <EmptyState
                    title={t(m.emptyTitle)}
                    body={t(demoHref ? m.emptyBody : m.emptyBodyNoDemo)}
                    illustration="organisations"
                    headingLevel={2}
                    actions={[
                      <Button key="create" variant="primary" onClick={() => setCreating(true)}>
                        {t(m.emptyCreate)}
                      </Button>,
                      ...(demoHref
                        ? [
                            <Button key="demo" onClick={() => go(demoHref)}>
                              {t(m.emptyDemo)}
                            </Button>,
                          ]
                        : []),
                    ]}
                  />
                }
                noResultsState={
                  <EmptyState
                    title={t(m.noResultsTitle)}
                    body={t(m.noResultsBody)}
                    illustration="search"
                    headingLevel={2}
                    actions={[
                      <Button
                        key="clear"
                        variant="primary"
                        onClick={() =>
                          setState((current) => ({
                            ...current,
                            q: "",
                            filters: {},
                            archived: false,
                          }))
                        }
                      >
                        {t(m.gridClear)}
                      </Button>,
                    ]}
                  />
                }
                errorState={
                  <ErrorState
                    title={t(m.errorTitle)}
                    body={t(m.errorBody)}
                    retryLabel={t(m.retry)}
                    onRetry={() => {
                      setStatus("loading");
                      setAttempt((n) => n + 1);
                    }}
                    headingLevel={2}
                  />
                }
              />
            )}
          </div>
        </div>
      </div>

      <p role="status" className="sr-only">
        {announcement}
      </p>
      {creating ? (
        <NewOrganisationDialog
          practice={practice}
          onClose={() => setCreating(false)}
          onCreated={(id) => go(orgModuleUrl(id, "home"))}
        />
      ) : null}
      {bulk ? (
        <BulkActionDialog
          practice={practice}
          action={bulk.action}
          selection={bulk.selection}
          onClose={() => setBulk(null)}
          onStarted={(job) => {
            setBulk(null);
            setSelection(EMPTY_SELECTION);
            setBulkJob(job);
          }}
        />
      ) : null}
      {bulkJob ? (
        <BulkProgressDrawer
          job={bulkJob}
          onClose={() => setBulkJob(null)}
          onFinished={() => setAttempt((n) => n + 1)}
        />
      ) : null}
    </div>
  );
}

function NewOrganisationDialog({
  practice,
  onClose,
  onCreated,
}: {
  practice: string;
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const t = useFormatMessage();
  const id = useId();
  const formId = useId();
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setError(t(m.createNameRequired));
      return;
    }
    setBusy(true);
    const result = await apiRequest<{ id?: string }>("/api/v1/organisations", {
      method: "POST",
      body: { name: name.trim(), practice },
    });
    setBusy(false);
    if (result.status === 201 && result.body.id) onCreated(result.body.id);
    else setError(t(m.createFailed));
  };
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={t(m.createTitle)}
      description={t(m.createBody)}
      closeLabel={t(m.close)}
      size="sm"
      footer={
        <>
          <Button onClick={onClose}>{t(m.cancel)}</Button>
          <Button variant="primary" type="submit" form={formId} loading={busy}>
            {t(m.createButton)}
          </Button>
        </>
      }
    >
      <form id={formId} onSubmit={submit} className="grid gap-1" noValidate>
        <label htmlFor={id} className="text-sm font-medium text-fg">
          {t(m.createName)}
        </label>
        <Input
          id={id}
          value={name}
          maxLength={200}
          autoFocus
          invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(event) => {
            setName(event.target.value);
            setError("");
          }}
        />
        {error ? (
          <p id={`${id}-error`} className="text-sm font-medium text-fg-danger">
            {error}
          </p>
        ) : null}
      </form>
    </Dialog>
  );
}
