"use client";

/**
 * Report runner (K-01-T13, wireframe 55): a sticky parameter bar built from the report's
 * parameter schema — date range presets (FYE-aware on the server) or custom dates, or a balance
 * date; comparisons (none / N previous periods / prior year, up to 12); the basis chip (the
 * organisation default from tax settings, or the override); the accounting/tax book switch; the
 * tracking filter — with **Update** (and Enter in any field). Then the report header (K-01-T06)
 * and the results in the design-system `ReportTable` (sticky header and first column, ⤢ drill on
 * each figure, compact view, windowed for long reports; a 12-column comparison scrolls inside the
 * table). Export menu: PDF, XLSX (also for Google Sheets), CSV — the same body as the screen.
 */
import {
  Badge,
  Button,
  ErrorState,
  ExplainPanel,
  Input,
  ReportTable,
  Select,
  Skeleton,
  Switch,
  type AppLocale,
  type ReportTableRow,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";

import { useFormatMessage } from "@/i18n";

import {
  EXPORT_FILES,
  exportUrl,
  reportsApi,
  type ReportBody,
  type ReportRowData,
  type ReportSummary,
} from "./api";
import {
  basisLabels,
  bookLabels,
  compareLabels,
  exportLabels,
  presetLabels,
  runner,
} from "./messages";

export const PRESETS = [
  "this_month",
  "last_month",
  "this_quarter",
  "last_quarter",
  "this_financial_year",
  "last_financial_year",
  "month_to_date",
  "quarter_to_date",
  "year_to_date",
  "custom",
] as const;
export const MAX_PERIODS = 12;

export type RunParams = Record<string, string>;

export interface DrillTarget {
  row: ReportRowData;
  column: number;
}

/** The query a run sends: a preset replaces the dates unless it is "custom". */
export function runQuery(report: ReportSummary, params: RunParams): RunParams {
  const names = new Set(report.params.map((p) => p.name));
  const query: RunParams = {};
  for (const [key, value] of Object.entries(params)) {
    if (!value) continue;
    if (key === "preset" || key === "layout" || names.has(key)) query[key] = value;
  }
  if (query.preset && query.preset !== "custom") {
    delete query.date_from;
    delete query.date_to;
  }
  if (query.compare === "none") delete query.periods;
  return query;
}

/** Starting parameters: the schema's defaults, a period report on this financial year. */
export function initialParams(report: ReportSummary, search?: URLSearchParams): RunParams {
  const params: RunParams = {};
  for (const spec of report.params) {
    if (spec.default !== null && spec.default !== "") params[spec.name] = String(spec.default);
  }
  const names = new Set(report.params.map((p) => p.name));
  if (names.has("date_from") && names.has("date_to")) params.preset = "this_financial_year";
  search?.forEach((value, key) => {
    if (key === "preset" || key === "layout" || names.has(key)) params[key] = value;
  });
  if (params.date_from && params.date_to && !search?.get("preset")) params.preset = "custom";
  return params;
}

export function toTableRows(body: ReportBody): ReportTableRow[] {
  return [...body.rows, ...body.totals].map((row) => ({
    key: row.key,
    label: row.label,
    kind: row.kind,
    level: row.level,
    values: row.values,
    drillable: row.drill !== null,
    notes: row.notes,
  }));
}

export interface ReportRunnerProps {
  org: string;
  slug: string;
  /** The drill-down drawer (K-01-T14) for a figure. */
  renderDrill?: (target: DrillTarget, body: ReportBody, close: () => void) => ReactNode;
  /** The layout editor panel (K-01-T15). */
  renderLayoutEditor?: (args: {
    report: ReportSummary;
    body: ReportBody;
    params: RunParams;
    close: () => void;
    reload: (layout?: string) => void;
  }) => ReactNode;
}

export function ReportRunner({ org, slug, renderDrill, renderLayoutEditor }: ReportRunnerProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [report, setReport] = useState<ReportSummary | null | undefined>(undefined);
  const [params, setParams] = useState<RunParams>({});
  const [body, setBody] = useState<ReportBody | null>(null);
  const [state, setState] = useState<"idle" | "running" | "failed" | "gated">("idle");
  const [gated, setGated] = useState("");
  const [compact, setCompact] = useState(false);
  const [drill, setDrill] = useState<DrillTarget | null>(null);
  const [editing, setEditing] = useState(false);

  const run = useCallback(
    async (definition: ReportSummary, next: RunParams) => {
      setState("running");
      const result = await reportsApi.run(org, definition.slug, runQuery(definition, next));
      if (result.status === 200 && Array.isArray(result.body?.rows)) {
        setBody(result.body);
        setState("idle");
      } else if (result.status === 402) {
        setGated(result.body?.product_name ?? definition.product_name);
        setState("gated");
      } else setState("failed");
    },
    [org],
  );

  useEffect(() => {
    let cancelled = false;
    void reportsApi.catalogue(org).then((result) => {
      if (cancelled) return;
      if (result.status !== 200 || !Array.isArray(result.body?.categories)) {
        setState("failed");
        setReport(null);
        return;
      }
      const found = result.body.categories
        .flatMap((group) => group.reports)
        .find((r) => r.slug === slug || r.id === slug);
      setReport(found ?? null);
      if (found) {
        const start = initialParams(found, new URLSearchParams(window.location.search));
        setParams(start);
        void run(found, start);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [org, slug, run]);

  const names = useMemo(() => new Set(report?.params.map((p) => p.name) ?? []), [report]);
  const set = (name: string, value: string) => setParams((p) => ({ ...p, [name]: value }));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (report) void run(report, params);
  };

  if (report === undefined && state !== "failed") {
    return (
      <div className="flex flex-col gap-4" aria-busy="true">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (!report) {
    return state === "failed" ? (
      <ErrorState
        title={fm(runner.failed)}
        body={fm(runner.failedBody)}
        retryLabel={fm(runner.retry)}
        onRetry={() => window.location.reload()}
      />
    ) : (
      <ExplainPanel
        kind="notFound"
        title={fm(runner.unknown)}
        body={fm(runner.unknownBody)}
        headingLevel={1}
        actions={[
          <Link key="home" href={`/o/${org}/reports`} className="text-sm font-semibold underline">
            {fm(runner.back)}
          </Link>,
        ]}
      />
    );
  }

  const header = body?.header;
  const periodReport = names.has("date_from") && names.has("date_to");
  const query = runQuery(report, params);
  const comparing = names.has("compare") && params.compare && params.compare !== "none";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <Link
            href={`/o/${org}/reports`}
            className="text-sm text-fg-muted underline underline-offset-2"
          >
            {fm(runner.back)}
          </Link>
          <h1 className="text-2xl font-bold text-fg">{report.name}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <details className="relative" data-export-menu="">
            <summary className="inline-flex h-10 cursor-pointer list-none items-center rounded-md border border-border-strong bg-surface px-4 text-sm font-semibold text-fg hover:bg-surface-muted">
              {fm(runner.export)}
            </summary>
            <ul className="absolute end-0 z-30 mt-1 flex min-w-72 flex-col rounded-md border border-border bg-surface p-1 shadow-elevation-2">
              {EXPORT_FILES.map((file) => (
                <li key={file}>
                  <a
                    href={exportUrl(org, report.slug, query, file)}
                    download
                    className="block rounded px-3 py-2 text-sm text-fg hover:bg-surface-muted"
                  >
                    {fm(exportLabels[file]!)}
                  </a>
                </li>
              ))}
            </ul>
          </details>
          {renderLayoutEditor ? (
            <Button variant="secondary" onClick={() => setEditing(true)} disabled={!body}>
              {fm(runner.editLayout)}
            </Button>
          ) : null}
        </div>
      </div>

      <form
        onSubmit={submit}
        aria-label={fm(runner.parameters)}
        className="sticky top-0 z-30 flex flex-wrap items-end gap-3 rounded-lg border border-border bg-surface-subtle p-3"
        data-param-bar=""
      >
        {periodReport ? (
          <>
            <label className="flex flex-col gap-1 text-xs font-semibold text-fg">
              {fm(runner.range)}
              <Select
                aria-label={fm(runner.range)}
                value={params.preset ?? "custom"}
                onValueChange={(value) => set("preset", value)}
                options={PRESETS.map((p) => ({ value: p, label: fm(presetLabels[p]!) }))}
              />
            </label>
            {params.preset === "custom" ? (
              <>
                <label className="flex flex-col gap-1 text-xs font-semibold text-fg">
                  {fm(runner.from)}
                  <Input
                    type="date"
                    value={params.date_from ?? ""}
                    onChange={(e) => set("date_from", e.target.value)}
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs font-semibold text-fg">
                  {fm(runner.to)}
                  <Input
                    type="date"
                    value={params.date_to ?? ""}
                    onChange={(e) => set("date_to", e.target.value)}
                  />
                </label>
              </>
            ) : null}
          </>
        ) : null}
        {names.has("as_of") ? (
          <label className="flex flex-col gap-1 text-xs font-semibold text-fg">
            {fm(runner.asOf)}
            <Input
              type="date"
              value={params.as_of ?? ""}
              onChange={(e) => set("as_of", e.target.value)}
            />
          </label>
        ) : null}
        {names.has("compare") ? (
          <label className="flex flex-col gap-1 text-xs font-semibold text-fg">
            {fm(runner.compare)}
            <Select
              aria-label={fm(runner.compare)}
              value={params.compare ?? "none"}
              onValueChange={(value) => set("compare", value)}
              options={["none", "previous", "prior_year"].map((c) => ({
                value: c,
                label: fm(compareLabels[c]!),
              }))}
            />
          </label>
        ) : null}
        {comparing && names.has("periods") ? (
          <label className="flex w-24 flex-col gap-1 text-xs font-semibold text-fg">
            {fm(runner.periods)}
            <Input
              type="number"
              min={1}
              max={MAX_PERIODS}
              value={params.periods ?? "1"}
              onChange={(e) => set("periods", e.target.value)}
            />
          </label>
        ) : null}
        {names.has("basis") ? (
          <label className="flex flex-col gap-1 text-xs font-semibold text-fg">
            {fm(runner.basis)}
            <Select
              aria-label={fm(runner.basis)}
              value={params.basis || "default"}
              onValueChange={(value) => set("basis", value === "default" ? "" : value)}
              options={["default", "accrual", "cash"].map((b) => ({
                value: b,
                label: fm(basisLabels[b]!),
              }))}
            />
          </label>
        ) : null}
        {names.has("book") ? (
          <div role="group" aria-label={fm(runner.book)} className="flex flex-col gap-1">
            <span className="text-xs font-semibold text-fg" aria-hidden="true">
              {fm(runner.book)}
            </span>
            <div className="flex">
              {["accounting", "tax"].map((book, i) => (
                <Button
                  key={book}
                  type="button"
                  size="sm"
                  variant={(params.book ?? "accounting") === book ? "primary" : "secondary"}
                  aria-pressed={(params.book ?? "accounting") === book}
                  className={i === 0 ? "rounded-e-none" : "rounded-s-none"}
                  onClick={() => set("book", book)}
                >
                  {fm(bookLabels[book]!)}
                </Button>
              ))}
            </div>
          </div>
        ) : null}
        {names.has("tracking") ? (
          <label className="flex flex-col gap-1 text-xs font-semibold text-fg">
            {fm(runner.tracking)}
            <Input
              value={params.tracking ?? ""}
              placeholder={fm(runner.trackingHint)}
              onChange={(e) => set("tracking", e.target.value)}
            />
          </label>
        ) : null}
        <Button type="submit" variant="primary" disabled={state === "running"}>
          {fm(runner.update)}
        </Button>
        <Switch checked={compact} onCheckedChange={setCompact} label={fm(runner.compact)} />
      </form>

      {state === "gated" ? (
        <ExplainPanel
          kind="gated"
          title={fm(runner.gated, { name: report.name, product: gated })}
          body={fm(runner.gatedBody)}
        />
      ) : state === "failed" ? (
        <ErrorState
          title={fm(runner.failed)}
          body={fm(runner.failedBody)}
          retryLabel={fm(runner.retry)}
          onRetry={() => void run(report, params)}
          headingLevel={2}
        />
      ) : null}

      {state === "running" && !body ? (
        <div aria-busy="true" role="status" className="flex flex-col gap-2">
          <span className="sr-only">{fm(runner.running)}</span>
          <Skeleton className="h-64 w-full" />
        </div>
      ) : null}

      {body && header && state !== "gated" ? (
        <section
          className="flex flex-col gap-3"
          aria-busy={state === "running"}
          data-report-body=""
        >
          <header className="flex flex-col gap-0.5" data-report-header="">
            <p className="text-lg font-semibold text-fg">{header.display_name}</p>
            {header.legal_name ? (
              <p className="text-sm text-fg-muted">{header.legal_name}</p>
            ) : null}
            <p className="text-sm text-fg">{header.period_label}</p>
            {header.status_label ? (
              <p className="text-sm font-semibold text-fg">{header.status_label}</p>
            ) : null}
            <div className="mt-1 flex flex-wrap gap-2">
              {header.basis_label ? <Badge tone="neutral">{header.basis_label}</Badge> : null}
              <Badge tone="neutral">{header.book_label}</Badge>
            </div>
            {body.layout ? (
              <p className="text-xs text-fg-muted">
                {fm(runner.layoutName, { name: body.layout.name, version: body.layout.version })}
                {body.layout.status === "published" ? (
                  <span className="ms-1">{fm(runner.publishedLayout)}</span>
                ) : null}
              </p>
            ) : null}
          </header>
          <ReportTable
            caption={header.title}
            columns={body.columns}
            rows={toTableRows(body)}
            locale={locale}
            compact={compact}
            labels={{
              drill: (row, column) => fm(runner.drill, { row, column }),
              note: fm(runner.note),
            }}
            onDrill={
              renderDrill
                ? (row, column) => {
                    const data = [...body.rows, ...body.totals].find((r) => r.key === row.key);
                    if (data) setDrill({ row: data, column });
                  }
                : undefined
            }
            footer={
              body.notes ? (
                <p className="whitespace-pre-line text-sm text-fg-muted" data-footnotes="">
                  {body.notes}
                </p>
              ) : null
            }
          />
        </section>
      ) : null}
      {drill && body && renderDrill ? renderDrill(drill, body, () => setDrill(null)) : null}
      {editing && body && renderLayoutEditor
        ? renderLayoutEditor({
            report,
            body,
            params,
            close: () => setEditing(false),
            reload: (layout) => {
              const next = { ...params };
              if (layout) next.layout = layout;
              setParams(next);
              void run(report, next);
            },
          })
        : null}
    </div>
  );
}
