"use client";

import {
  Button,
  Checkbox,
  DataGrid,
  DatePicker,
  Drawer,
  EmptyState,
  ExplainPanel,
  formatDate,
  Input,
  Select,
  todayIn,
  type AppLocale,
  type DataGridColumn,
  type DataGridLabels,
  type DatePickerLabels,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useState } from "react";

import { PermissionExplain } from "@/components/PermissionExplain";
import { useFormatMessage } from "@/i18n";
import type { ApiError } from "@/settings/users-roles/api";

import {
  EXPORT_FORMATS,
  exportUrl,
  getEvent,
  getFilterChoices,
  isAuditError,
  listEvents,
  type AuditEvent,
  type AuditFilterChoices,
  type AuditFilters,
  type AuditPage,
  type AuditViewer,
  type ExportFormat,
} from "./api";
import { DiffViewer } from "./DiffViewer";
import { m, presetLabels } from "./messages";
import { DEFAULT_PRESET, PRESETS, presetOf, presetRange, type Preset } from "./presets";
import { auditDateTime } from "./time";

const ANY = "__any__";

type Status =
  | { kind: "loading" }
  | { kind: "ready" }
  | { kind: "denied"; error: ApiError }
  | { kind: "notFound" }
  | { kind: "failed" };

export interface AuditLogScreenProps {
  org: string;
  /** Filters from the page URL (`?batch=…`, links from the record history drawer). */
  initial?: AuditFilters;
}

function useGridLabels(): DataGridLabels {
  const fm = useFormatMessage();
  return {
    grid: fm(m.grid),
    search: fm(m.gridSearch),
    columns: fm(m.gridColumns),
    density: fm(m.gridDensity),
    comfortable: fm(m.gridComfortable),
    compact: fm(m.gridCompact),
    filterAll: fm(m.gridAll),
    filterChip: (column, value) => fm(m.gridChip, { column, value }),
    clearFilters: fm(m.gridClear),
    selectAll: fm(m.gridSelectAll),
    selectRow: (row) => fm(m.gridSelectRow, { row }),
    selectedCount: (count) => fm(m.gridSelected, { count }),
    clearSelection: fm(m.gridClearSelection),
    resultCount: (shown, total) => fm(m.gridResults, { shown, total }),
    loading: fm(m.loading),
  };
}

function useDateLabels(): DatePickerLabels {
  const fm = useFormatMessage();
  return {
    openCalendar: fm(m.openCalendar),
    previousMonth: fm(m.previousMonth),
    nextMonth: fm(m.nextMonth),
    unreadable: fm(m.unreadable),
    shortcuts: {
      today: fm(presetLabels.today),
      plus7: "",
      plus14: "",
      plus30: "",
      endOfMonth: "",
      endOfNextMonth: "",
    },
  };
}

/**
 * Settings → Audit log (A-04-T09): the organisation's global audit viewer. Date presets (Today,
 * Last 7/30/90 days, This month, This quarter, This fiscal year, custom; default Last 90 days),
 * filters (user, record types, action, text), the events in a DataGrid newest first with
 * "Show older events" (cursor pages), each event's DiffViewer in a drawer, and the export menu —
 * CSV / XLSX / PDF with the same filters, so a file holds exactly the rows listed.
 */
export function AuditLogScreen({ org, initial = {} }: Readonly<AuditLogScreenProps>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [filters, setFilters] = useState<AuditFilters>(initial);
  const [draft, setDraft] = useState<AuditFilters>(initial);
  const [rows, setRows] = useState<AuditEvent[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [range, setRange] = useState<AuditPage["range"] | null>(null);
  const [viewer, setViewer] = useState<AuditViewer | null>(null);
  const [status, setStatus] = useState<Status>({ kind: "loading" });
  const [more, setMore] = useState(false);
  const [choices, setChoices] = useState<AuditFilterChoices | null>(null);
  const [open, setOpen] = useState<AuditEvent | null>(null);
  const [formKey, setFormKey] = useState(0);

  const load = useCallback(
    async (current: AuditFilters) => {
      setStatus({ kind: "loading" });
      const answer = await listEvents(org, current);
      if (answer.status === 404) return setStatus({ kind: "notFound" });
      if (answer.status === 403 && isAuditError(answer.body)) {
        return setStatus({ kind: "denied", error: answer.body as ApiError });
      }
      if (answer.status !== 200 || isAuditError(answer.body)) return setStatus({ kind: "failed" });
      setRows(answer.body.results);
      setNext(answer.body.next);
      setRange(answer.body.range);
      setViewer(answer.body.viewer);
      setStatus({ kind: "ready" });
    },
    [org],
  );

  useEffect(() => {
    void load(filters);
  }, [load, filters]);

  useEffect(() => {
    void getFilterChoices(org).then((answer) => {
      if (answer.status === 200 && !isAuditError(answer.body)) setChoices(answer.body);
    });
  }, [org]);

  const loadMore = async () => {
    if (!next) return;
    setMore(true);
    const answer = await listEvents(org, filters, next);
    setMore(false);
    if (answer.status !== 200 || isAuditError(answer.body)) return setStatus({ kind: "failed" });
    const older = answer.body;
    setRows((current) => [...current, ...older.results]);
    setNext(older.next);
  };

  const openEvent = async (row: AuditEvent) => {
    setOpen(row);
    const full = await getEvent(org, row.id);
    if (full.status === 200 && !isAuditError(full.body)) setOpen(full.body);
  };

  const showBatch = (batch: string) => {
    setOpen(null);
    const scoped: AuditFilters = batch ? { batch, from: range?.from, to: range?.to } : {};
    setDraft(scoped);
    setFilters(scoped);
    setFormKey((n) => n + 1);
  };

  if (status.kind === "denied") {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-semibold">{fm(m.title)}</h1>
        <PermissionExplain org={org} error={status.error} />
      </div>
    );
  }
  if (status.kind === "notFound") {
    return (
      <ExplainPanel
        kind="notFound"
        headingLevel={1}
        title={fm(m.notFoundTitle)}
        body={fm(m.notFoundBody)}
      />
    );
  }

  const today = todayIn(viewer?.time_zone ?? range?.time_zone);
  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">{fm(m.title)}</h1>
        <p className="text-fg-muted">{fm(m.intro)}</p>
      </header>
      <FilterForm
        key={formKey}
        draft={draft}
        today={today}
        locale={locale}
        choices={choices}
        onChange={setDraft}
        onApply={() => setFilters({ ...draft })}
        onReset={() => {
          setDraft({});
          setFilters({});
          setFormKey((n) => n + 1);
        }}
      />
      <div className="flex flex-wrap items-center gap-3">
        {range ? (
          <p className="text-sm text-fg-muted" data-audit-range="">
            {fm(m.rangeShown, {
              from: formatDate(range.from, { locale }),
              to: formatDate(range.to, { locale }),
              zone: range.time_zone,
            })}
          </p>
        ) : null}
        {filters.batch ? (
          <p className="flex flex-wrap items-center gap-2 text-sm" role="status">
            {fm(m.batchShown)}
            <Button size="sm" variant="ghost" onClick={() => showBatch("")}>
              {fm(m.showAll)}
            </Button>
          </p>
        ) : null}
        <div className="ms-auto">
          <ExportMenu org={org} filters={filters} />
        </div>
      </div>
      {status.kind === "failed" ? (
        <p role="alert" className="text-fg-danger">
          {fm(m.loadFailed)}
        </p>
      ) : null}
      <EventGrid
        rows={rows}
        locale={locale}
        viewer={viewer}
        loading={status.kind === "loading"}
        onOpen={(row) => void openEvent(row)}
      />
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-sm text-fg-muted" role="status">
          {status.kind === "ready" ? fm(m.shown, { count: rows.length }) : ""}
          {status.kind === "ready" && !next && rows.length > 0 ? (
            <span className="ms-1">{fm(m.allShown)}</span>
          ) : null}
        </p>
        {next ? (
          <Button variant="secondary" loading={more} onClick={() => void loadMore()}>
            {fm(m.loadMore)}
          </Button>
        ) : null}
      </div>
      {open ? (
        <EventDrawer
          event={open}
          locale={locale}
          viewer={viewer}
          onClose={() => setOpen(null)}
          onShowBatch={showBatch}
        />
      ) : null}
    </div>
  );
}

// ---- filters --------------------------------------------------------------------------------

function FilterForm({
  draft,
  today,
  locale,
  choices,
  onChange,
  onApply,
  onReset,
}: Readonly<{
  draft: AuditFilters;
  today: string;
  locale: AppLocale;
  choices: AuditFilterChoices | null;
  onChange: (filters: AuditFilters) => void;
  onApply: () => void;
  onReset: () => void;
}>) {
  const fm = useFormatMessage();
  const dateLabels = useDateLabels();
  const ids = { preset: useId(), from: useId(), to: useId(), user: useId(), action: useId() };
  const searchId = useId();
  const typesId = useId();
  const preset: Preset =
    draft.from || draft.to
      ? presetOf({ from: draft.from ?? draft.to!, to: draft.to ?? today }, today)
      : DEFAULT_PRESET;
  const [custom, setCustom] = useState(preset === "custom");
  const shownPreset = custom ? "custom" : preset;
  const choosePreset = (value: string) => {
    if (value === "custom") {
      setCustom(true);
      const current = draft.from ? draft : { ...draft, ...presetRange(DEFAULT_PRESET, today) };
      onChange(current);
      return;
    }
    setCustom(false);
    if (value === DEFAULT_PRESET) {
      onChange({ ...draft, from: undefined, to: undefined });
    } else {
      onChange({ ...draft, ...presetRange(value as Exclude<Preset, "custom">, today) });
    }
  };
  const types = new Set(draft.type ?? []);
  return (
    <form
      aria-label={fm(m.filters)}
      className="flex flex-wrap items-end gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <div className="flex w-full flex-col gap-1 sm:w-48">
        <label htmlFor={ids.preset} className="text-sm font-medium">
          {fm(m.dates)}
        </label>
        <Select
          id={ids.preset}
          value={shownPreset}
          onValueChange={choosePreset}
          options={PRESETS.map((p) => ({ value: p, label: fm(presetLabels[p]) }))}
        />
      </div>
      {shownPreset === "custom" ? (
        <>
          <div className="flex w-full flex-col gap-1 sm:w-44">
            <label htmlFor={ids.from} className="text-sm font-medium">
              {fm(m.from)}
            </label>
            <DatePicker
              id={ids.from}
              value={draft.from ?? null}
              onChange={(value) => onChange({ ...draft, from: value ?? undefined })}
              locale={locale}
              today={today}
              max={draft.to ?? today}
              labels={dateLabels}
              shortcuts={[]}
            />
          </div>
          <div className="flex w-full flex-col gap-1 sm:w-44">
            <label htmlFor={ids.to} className="text-sm font-medium">
              {fm(m.to)}
            </label>
            <DatePicker
              id={ids.to}
              value={draft.to ?? null}
              onChange={(value) => onChange({ ...draft, to: value ?? undefined })}
              locale={locale}
              today={today}
              min={draft.from}
              max={today}
              labels={dateLabels}
              shortcuts={[]}
            />
          </div>
        </>
      ) : null}
      <div className="flex w-full flex-col gap-1 sm:w-56">
        <label htmlFor={ids.user} className="text-sm font-medium">
          {fm(m.user)}
        </label>
        <Select
          id={ids.user}
          value={draft.user || ANY}
          onValueChange={(value) => onChange({ ...draft, user: value === ANY ? "" : value })}
          options={[
            { value: ANY, label: fm(m.everyone) },
            ...(choices?.users ?? []).map((u) => ({ value: u.value, label: u.label })),
          ]}
        />
      </div>
      <div className="flex w-full flex-col gap-1 sm:w-56">
        <span id={typesId} className="text-sm font-medium">
          {fm(m.types)}
        </span>
        <details className="relative" data-audit-types="">
          <summary
            aria-describedby={typesId}
            className="flex min-h-touch-target cursor-pointer items-center rounded-md border border-border px-3 text-sm"
          >
            {types.size === 0 ? fm(m.allTypes) : fm(m.someTypes, { count: types.size })}
          </summary>
          <fieldset
            aria-labelledby={typesId}
            className="z-10 mt-1 flex max-h-64 flex-col gap-2 overflow-y-auto rounded-md border border-border bg-surface p-3 sm:absolute sm:w-72"
          >
            {(choices?.types ?? []).map((option) => (
              <label key={option.value} className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={types.has(option.value)}
                  onCheckedChange={(on) => {
                    const nextTypes = new Set(types);
                    if (on === true) nextTypes.add(option.value);
                    else nextTypes.delete(option.value);
                    onChange({ ...draft, type: [...nextTypes] });
                  }}
                />
                {option.label}
              </label>
            ))}
          </fieldset>
        </details>
      </div>
      <div className="flex w-full flex-col gap-1 sm:w-44">
        <label htmlFor={ids.action} className="text-sm font-medium">
          {fm(m.action)}
        </label>
        <Select
          id={ids.action}
          value={draft.action || ANY}
          onValueChange={(value) => onChange({ ...draft, action: value === ANY ? "" : value })}
          options={[
            { value: ANY, label: fm(m.anyAction) },
            ...(choices?.actions ?? []).map((a) => ({ value: a.value, label: a.label })),
          ]}
        />
      </div>
      <div className="flex w-full min-w-48 flex-1 flex-col gap-1 sm:w-auto">
        <label htmlFor={searchId} className="text-sm font-medium">
          {fm(m.search)}
        </label>
        <Input
          id={searchId}
          type="search"
          value={draft.q ?? ""}
          placeholder={fm(m.searchHint)}
          onChange={(event) => onChange({ ...draft, q: event.target.value })}
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit">{fm(m.apply)}</Button>
        <Button type="button" variant="ghost" onClick={onReset}>
          {fm(m.reset)}
        </Button>
      </div>
    </form>
  );
}

// ---- export menu ------------------------------------------------------------------------------

const FORMAT_LABEL = { csv: m.exportCsv, xlsx: m.exportXlsx, pdf: m.exportPdf } as const;

function ExportMenu({ org, filters }: Readonly<{ org: string; filters: AuditFilters }>) {
  const fm = useFormatMessage();
  const noteId = useId();
  return (
    <details className="relative" data-audit-export="">
      <summary className="flex min-h-touch-target cursor-pointer items-center rounded-md border border-border px-4 text-sm font-semibold">
        {fm(m.export)}
      </summary>
      <div className="absolute end-0 z-10 mt-1 flex w-64 flex-col gap-1 rounded-md border border-border bg-surface p-2 shadow-elevation-2">
        <p id={noteId} className="px-2 py-1 text-xs text-fg-muted">
          {fm(m.exportNote)}
        </p>
        <ul aria-describedby={noteId} className="flex flex-col">
          {EXPORT_FORMATS.map((format: ExportFormat) => (
            <li key={format}>
              <a
                href={exportUrl(org, format, filters)}
                download
                className="flex min-h-touch-target items-center rounded px-2 text-sm hover:bg-surface-subtle"
                data-export-format={format}
              >
                {fm(FORMAT_LABEL[format])}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}

// ---- the grid ----------------------------------------------------------------------------------

function EventGrid({
  rows,
  locale,
  viewer,
  loading,
  onOpen,
}: Readonly<{
  rows: AuditEvent[];
  locale: AppLocale;
  viewer: AuditViewer | null;
  loading: boolean;
  onOpen: (row: AuditEvent) => void;
}>) {
  const fm = useFormatMessage();
  const labels = useGridLabels();
  const columns = useMemo<DataGridColumn<AuditEvent>[]>(
    () => [
      {
        id: "at",
        header: fm(m.colWhen),
        accessor: (row) => row.at,
        cell: (row) => (
          <time dateTime={row.at} data-audit-time="">
            {auditDateTime(row.at, { locale, viewer })}
          </time>
        ),
        width: 200,
        hideable: false,
        searchable: false,
      },
      { id: "user", header: fm(m.colUser), accessor: (row) => row.actor.label, width: 220 },
      {
        id: "action",
        header: fm(m.colAction),
        accessor: (row) => row.action_label,
        width: 170,
      },
      {
        id: "type",
        header: fm(m.colType),
        accessor: (row) => row.record.type_label,
        width: 160,
      },
      { id: "record", header: fm(m.colRecord), accessor: (row) => row.record.label, width: 220 },
      {
        id: "changes",
        header: fm(m.colChanges),
        accessor: (row) =>
          row.is_batch_summary
            ? fm(m.batchCount, { count: Number(row.meta.events ?? 0) })
            : fm(m.changeCount, {
                count: row.changes.length,
                fields: row.changes.map((c) => c.label).join(", "),
              }),
      },
    ],
    [fm, locale, viewer],
  );
  return (
    <DataGrid
      data={rows}
      columns={columns}
      getRowId={(row) => row.id}
      getRowLabel={(row) => `${row.action_label} ${row.record.label}`}
      labels={labels}
      onRowOpen={onOpen}
      status={loading ? "loading" : "ready"}
      emptyState={<EmptyState title={fm(m.empty)} body={fm(m.emptyHint)} headingLevel={2} />}
      height={520}
    />
  );
}

// ---- one event --------------------------------------------------------------------------------

function EventDrawer({
  event,
  locale,
  viewer,
  onClose,
  onShowBatch,
}: Readonly<{
  event: AuditEvent;
  locale: AppLocale;
  viewer: AuditViewer | null;
  onClose: () => void;
  onShowBatch: (batch: string) => void;
}>) {
  const fm = useFormatMessage();
  const job = event.meta.job as
    { id?: string; task?: string; started_by?: { label?: string } } | undefined;
  return (
    <Drawer
      open
      onOpenChange={(state) => (state ? undefined : onClose())}
      title={fm(m.detailTitle, {
        action: event.action_label,
        record: event.record.label || fm(m.none),
      })}
      closeLabel={fm(m.close)}
      size="lg"
    >
      <dl className="mb-4 grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-[9rem_1fr]">
        <dt className="font-medium">{fm(m.when)}</dt>
        <dd>
          <time dateTime={event.at}>{auditDateTime(event.at, { locale, viewer })}</time>
        </dd>
        <dt className="font-medium">{fm(m.by)}</dt>
        <dd>
          {event.actor.label}
          {event.actor.impersonator ? (
            <span className="block text-fg-muted">
              {fm(m.impersonated, { name: event.actor.impersonator.name })}
            </span>
          ) : null}
        </dd>
        {job ? (
          <>
            <dt className="font-medium">{fm(m.job)}</dt>
            <dd className="break-all">
              <span className="font-mono text-xs">{job.task}</span>
              {job.started_by?.label ? (
                <span className="block text-fg-muted">
                  {fm(m.startedBy, { name: job.started_by.label })}
                </span>
              ) : null}
            </dd>
          </>
        ) : null}
        <dt className="font-medium">{fm(m.recordType)}</dt>
        <dd>{event.record.type_label || fm(m.none)}</dd>
        <dt className="font-medium">{fm(m.ip)}</dt>
        <dd>{event.ip ?? fm(m.none)}</dd>
        <dt className="font-medium">{fm(m.device)}</dt>
        <dd className="break-all">{event.device || fm(m.none)}</dd>
        <dt className="font-medium">{fm(m.requestId)}</dt>
        <dd className="font-mono text-xs break-all">{event.request_id || fm(m.none)}</dd>
        <dt className="font-medium">{fm(m.eventId)}</dt>
        <dd className="font-mono text-xs break-all">{event.id}</dd>
      </dl>
      {event.is_batch_summary && event.batch_id ? (
        <Button variant="secondary" onClick={() => onShowBatch(event.batch_id!)}>
          {fm(m.openBatch, { count: Number(event.meta.events ?? 0) })}
        </Button>
      ) : (
        <DiffViewer changes={event.changes} />
      )}
    </Drawer>
  );
}
