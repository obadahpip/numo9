"use client";

/**
 * Report home (K-01-T12, wireframe 54): search by name, description and category; category
 * filters (All, Favourites, then the catalogue's categories); tabs Standard · Drafts · Published ·
 * Custom (saved layouts, K-01-T08); a description toggle remembered per person; a ★ per report
 * (favourites, per person). A report whose product the package lacks is listed with the product
 * named — gated, never hidden (gap-14).
 */
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Input,
  Skeleton,
  Switch,
  Tabs,
  cn,
} from "@numo9/ui";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useFormatMessage, type FormatMessage } from "@/i18n";

import { reportsApi, type Catalogue, type ReportLayout, type ReportSummary } from "./api";
import { categoryLabels, home } from "./messages";

const DESCRIPTIONS_KEY = "numo9.reports.descriptions";

export function reportUrl(org: string, slug: string, layout?: string): string {
  return `/o/${org}/reports/${slug}${layout ? `?layout=${encodeURIComponent(layout)}` : ""}`;
}

/** Words a search matches: name, description, category key and its label. */
export function matchesReport(report: ReportSummary, query: string, categoryLabel = ""): boolean {
  const words = query.toLocaleLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const text = [report.name, report.description, report.category, categoryLabel, report.slug]
    .join(" ")
    .toLocaleLowerCase();
  return words.every((word) => text.includes(word));
}

function categoryName(fm: FormatMessage, key: string): string {
  const label = categoryLabels[key];
  return label ? fm(label) : key;
}

function readDescriptions(): boolean {
  try {
    return window.localStorage.getItem(DESCRIPTIONS_KEY) !== "off";
  } catch {
    return true;
  }
}

function StarIcon({ filled }: { filled: boolean }) {
  return (
    <svg viewBox="0 0 20 20" className="size-5" aria-hidden="true">
      <path
        d="M10 2.5l2.3 4.7 5.2.8-3.8 3.7.9 5.2L10 14.4l-4.6 2.5.9-5.2L2.5 8l5.2-.8z"
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function ReportsHome({ org }: { org: string }) {
  const fm = useFormatMessage();
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [tab, setTab] = useState("standard");
  const [descriptions, setDescriptions] = useState(true);

  useEffect(() => setDescriptions(readDescriptions()), []);
  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    void reportsApi.catalogue(org).then((result) => {
      if (cancelled) return;
      if (result.status === 200 && Array.isArray(result.body?.categories))
        setCatalogue(result.body);
      else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [org, attempt]);

  const toggleDescriptions = (on: boolean) => {
    setDescriptions(on);
    try {
      window.localStorage.setItem(DESCRIPTIONS_KEY, on ? "on" : "off");
    } catch {
      /* private mode: the toggle still works for this visit */
    }
  };

  const toggleFavourite = useCallback(
    async (report: ReportSummary) => {
      const on = !report.favourite;
      const flip = (c: Catalogue): Catalogue => ({
        ...c,
        favourites: on ? [...c.favourites, report.id] : c.favourites.filter((f) => f !== report.id),
        categories: c.categories.map((group) => ({
          ...group,
          reports: group.reports.map((r) => (r.id === report.id ? { ...r, favourite: on } : r)),
        })),
      });
      setCatalogue((c) => (c ? flip(c) : c));
      const result = await reportsApi.favourite(org, report.slug, on);
      if (result.status !== 204 && result.status !== 200) {
        setCatalogue((c) => (c ? revert(c, report, !on) : c));
      }
    },
    [org],
  );

  const reports = useMemo(
    () => (catalogue ? catalogue.categories.flatMap((group) => group.reports) : []),
    [catalogue],
  );
  const shown = useMemo(() => {
    const list = reports.filter(
      (r) =>
        (category === "all" ||
          (category === "favourites" ? r.favourite : r.category === category)) &&
        matchesReport(r, query, categoryName(fm, r.category)),
    );
    // Favourites first, then by name (the search result order of the wireframe).
    return [...list].sort(
      (a, b) => Number(b.favourite) - Number(a.favourite) || a.name.localeCompare(b.name),
    );
  }, [reports, category, query, fm]);

  const header = (
    <div className="flex max-w-3xl flex-col gap-1">
      <h1 className="text-2xl font-bold text-fg">{fm(home.title)}</h1>
      <p className="text-sm text-fg-muted">{fm(home.intro)}</p>
    </div>
  );

  if (failed) {
    return (
      <div className="flex flex-col gap-6">
        {header}
        <ErrorState
          title={fm(home.loadFailed)}
          body={fm(home.loadFailedBody)}
          retryLabel={fm(home.retry)}
          onRetry={() => setAttempt((n) => n + 1)}
          headingLevel={2}
        />
      </div>
    );
  }
  if (catalogue === null) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true">
        {header}
        <Skeleton className="h-10 w-full max-w-md" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  const names = new Map(reports.map((r) => [r.id, r]));
  const filters = ["all", "favourites", ...catalogue.categories.map((c) => c.key)];

  const standard = (
    <div className="flex flex-col gap-4">
      <div role="group" aria-label={fm(home.categories)} className="flex flex-wrap gap-2">
        {filters.map((key) => (
          <Button
            key={key}
            size="sm"
            variant={category === key ? "primary" : "secondary"}
            aria-pressed={category === key}
            onClick={() => setCategory(key)}
          >
            {key === "all"
              ? fm(home.all)
              : key === "favourites"
                ? fm(home.favourites)
                : categoryName(fm, key)}
          </Button>
        ))}
      </div>
      {shown.length === 0 ? (
        <p className="text-sm text-fg-muted" role="status">
          {category === "favourites" && !query
            ? fm(home.noFavourites)
            : fm(home.noMatch, { query })}
        </p>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2" aria-label={fm(home.title)}>
          {shown.map((report) => (
            <li
              key={report.id}
              className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface p-4"
              data-report={report.id}
            >
              <div className="flex min-w-0 flex-col gap-1">
                <Link
                  href={reportUrl(org, report.slug)}
                  className="font-semibold text-fg underline-offset-2 hover:underline"
                >
                  {report.name}
                </Link>
                <span className="text-xs text-fg-muted">{categoryName(fm, report.category)}</span>
                {descriptions && report.description ? (
                  <p className="text-sm text-fg-muted">{report.description}</p>
                ) : null}
                {!report.available ? (
                  <Badge tone="warning">{fm(home.gated, { product: report.product_name })}</Badge>
                ) : null}
              </div>
              <button
                type="button"
                className={cn(
                  "inline-flex size-touch-target shrink-0 items-center justify-center rounded-md hover:bg-surface-muted",
                  report.favourite ? "text-fg" : "text-fg-muted",
                )}
                aria-pressed={report.favourite}
                aria-label={fm(report.favourite ? home.unstar : home.star, { name: report.name })}
                onClick={() => void toggleFavourite(report)}
              >
                <StarIcon filled={report.favourite} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  const layoutList = (layouts: ReportLayout[]) =>
    layouts.length === 0 ? (
      <EmptyState compact headingLevel={3} title={fm(home.noLayouts)} />
    ) : (
      <ul className="flex flex-col gap-2">
        {layouts.map((layout) => {
          const report = names.get(layout.report);
          return (
            <li key={layout.id} className="rounded-lg border border-border bg-surface p-3">
              <Link
                href={reportUrl(org, report?.slug ?? layout.report, layout.id)}
                className="font-semibold text-fg underline-offset-2 hover:underline"
              >
                {layout.name}
              </Link>
              <p className="text-xs text-fg-muted">
                {fm(home.layoutVersion, {
                  report: report?.name ?? layout.report,
                  version: layout.version,
                })}
              </p>
            </li>
          );
        })}
      </ul>
    );

  return (
    <div className="flex flex-col gap-6">
      {header}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <label className="flex w-full max-w-md flex-col gap-1 text-sm font-semibold text-fg">
          {fm(home.search)}
          <Input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            autoComplete="off"
          />
        </label>
        <Switch
          checked={descriptions}
          onCheckedChange={toggleDescriptions}
          label={fm(home.showDescriptions)}
        />
      </div>
      <Tabs
        label={fm(home.tabs)}
        value={tab}
        onValueChange={setTab}
        items={[
          { value: "standard", label: fm(home.standard), content: standard },
          {
            value: "drafts",
            label: fm(home.drafts),
            count: catalogue.drafts.length,
            content: layoutList(catalogue.drafts),
          },
          {
            value: "published",
            label: fm(home.published),
            count: catalogue.published.length,
            content: layoutList(catalogue.published),
          },
          {
            value: "custom",
            label: fm(home.custom),
            count: catalogue.custom.length,
            content: layoutList(catalogue.custom),
          },
        ]}
      />
    </div>
  );
}

function revert(c: Catalogue, report: ReportSummary, on: boolean): Catalogue {
  return {
    ...c,
    favourites: on ? [...c.favourites, report.id] : c.favourites.filter((f) => f !== report.id),
    categories: c.categories.map((group) => ({
      ...group,
      reports: group.reports.map((r) => (r.id === report.id ? { ...r, favourite: on } : r)),
    })),
  };
}
