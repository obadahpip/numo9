"use client";

/**
 * Practice home (V-04-T08, wireframe 37): a grid of cards — a large number, its label and a link
 * that opens the directory with the same filters (its count equals the card's number; zero shows
 * "0") — then the next 30 days' deadlines and the workload per staff member. A card whose
 * provider failed shows its own error with **Try again**; the rest of the page still loads.
 * Practice-wide roles switch between their own organisations and the whole practice.
 * "Customise dashboard" (V-04-T09) reorders and hides cards, saved per person and practice.
 */
import { Button, ErrorState, formatDate, SkeletonText, type AppLocale } from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";
import { orgModuleUrl, practiceDirectoryFilteredUrl } from "@/routing/routes";

import {
  dashboardApi,
  type Dashboard,
  type DashboardScope,
  type DashboardWidget,
  type DeadlineItem,
  type WorkloadItem,
} from "./api";
import { m } from "./messages";

export function PracticeHomeScreen({ practice }: { practice: string }) {
  const fm = useFormatMessage();
  const [data, setData] = useState<Dashboard | null>(null);
  const [failed, setFailed] = useState(false);
  const [scope, setScope] = useState<DashboardScope | undefined>(undefined);
  const [attempt, setAttempt] = useState(0);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    let cancelled = false;
    void dashboardApi.get(practice, scope).then((result) => {
      if (cancelled) return;
      if (result.status === 200 && Array.isArray(result.body?.widgets)) {
        setData(result.body);
        setFailed(false);
      } else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [practice, scope, attempt]);

  /** One card's retry: ask again and take that card's new answer only. */
  const retryWidget = useCallback(
    async (key: string) => {
      setRetrying(key);
      const result = await dashboardApi.get(practice, data?.scope);
      setRetrying(null);
      if (result.status !== 200 || !Array.isArray(result.body?.widgets)) return;
      const fresh = result.body.widgets.find((w) => w.key === key);
      if (!fresh) return;
      setData((current) =>
        current
          ? { ...current, widgets: current.widgets.map((w) => (w.key === key ? fresh : w)) }
          : current,
      );
    },
    [practice, data?.scope],
  );

  const header = (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex max-w-3xl flex-col gap-1">
        <h1 className="text-2xl font-bold text-fg">{fm(m.title)}</h1>
        <p className="text-sm text-fg-muted">{fm(m.intro)}</p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {data && data.scopes.length > 1 ? (
          <ScopeSwitch value={data.scope} onChange={setScope} />
        ) : null}
        {data && !editing ? (
          <Button variant="secondary" onClick={() => setEditing(true)}>
            {fm(m.customise)}
          </Button>
        ) : null}
      </div>
    </div>
  );

  if (failed) {
    return (
      <div className="flex flex-col gap-6">
        {header}
        <ErrorState
          title={fm(m.loadFailed)}
          body={fm(m.loadFailedBody)}
          retryLabel={fm(m.retry)}
          onRetry={() => setAttempt((n) => n + 1)}
          headingLevel={2}
        />
      </div>
    );
  }
  if (!data) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true">
        {header}
        <p className="sr-only">{fm(m.loading)}</p>
        <SkeletonText lines={4} />
      </div>
    );
  }

  const shown = data.widgets.filter((w) => !w.hidden);
  const counts = shown.filter((w) => w.kind === "count");
  const lists = shown.filter((w) => w.kind !== "count");
  return (
    <div className="flex flex-col gap-6" data-practice-home="">
      {header}
      <p role="status" className="sr-only">
        {status}
      </p>
      {editing ? (
        <CustomisePanel
          widgets={data.widgets}
          onCancel={() => setEditing(false)}
          onSave={async (order, hidden) => {
            const result = await dashboardApi.saveLayout(practice, { order, hidden });
            if (result.status !== 200) return false;
            const rank = new Map(order.map((key, index) => [key, index]));
            setData({
              ...data,
              layout: { order, hidden },
              widgets: [...data.widgets]
                .sort((a, b) => (rank.get(a.key) ?? 99) - (rank.get(b.key) ?? 99))
                .map((w) => ({ ...w, hidden: hidden.includes(w.key) })),
            });
            setEditing(false);
            setStatus(fm(m.saved));
            return true;
          }}
        />
      ) : null}
      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5" data-cards="">
        {counts.map((widget) => (
          <li key={widget.key}>
            <CountCard
              practice={practice}
              widget={widget}
              busy={retrying === widget.key}
              onRetry={() => void retryWidget(widget.key)}
            />
          </li>
        ))}
      </ul>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {lists.map((widget) => (
          <ListPanel
            key={widget.key}
            widget={widget}
            busy={retrying === widget.key}
            onRetry={() => void retryWidget(widget.key)}
          />
        ))}
      </div>
    </div>
  );
}

function CustomisePanel({
  widgets,
  onSave,
  onCancel,
}: {
  widgets: DashboardWidget[];
  onSave: (order: string[], hidden: string[]) => Promise<boolean>;
  onCancel: () => void;
}) {
  const fm = useFormatMessage();
  const heading = useId();
  const [order, setOrder] = useState(widgets.map((w) => w.key));
  const [hidden, setHidden] = useState(new Set(widgets.filter((w) => w.hidden).map((w) => w.key)));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const title = new Map(widgets.map((w) => [w.key, w.title]));
  const move = (index: number, by: number) =>
    setOrder((keys) => {
      const next = [...keys];
      const [item] = next.splice(index, 1);
      next.splice(index + by, 0, item as string);
      return next;
    });
  return (
    <section
      aria-labelledby={heading}
      className="flex flex-col gap-3 rounded-lg border border-border-accent p-4"
      data-customise=""
    >
      <h2 id={heading} className="text-lg font-semibold text-fg">
        {fm(m.customiseTitle)}
      </h2>
      <p className="text-sm text-fg-muted">{fm(m.customiseIntro)}</p>
      <ol className="flex flex-col gap-2">
        {order.map((key, index) => {
          const name = title.get(key) ?? key;
          return (
            <li key={key} className="flex flex-wrap items-center gap-2" data-layout-item={key}>
              <label className="flex flex-1 items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={!hidden.has(key)}
                  aria-label={fm(m.show, { title: name })}
                  onChange={(event) =>
                    setHidden((current) => {
                      const next = new Set(current);
                      if (event.target.checked) next.delete(key);
                      else next.add(key);
                      return next;
                    })
                  }
                />
                <span>{name}</span>
              </label>
              <Button
                size="sm"
                variant="ghost"
                disabled={index === 0}
                aria-label={fm(m.moveUp, { title: name })}
                onClick={() => move(index, -1)}
              >
                {fm(m.up)}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={index === order.length - 1}
                aria-label={fm(m.moveDown, { title: name })}
                onClick={() => move(index, 1)}
              >
                {fm(m.down)}
              </Button>
            </li>
          );
        })}
      </ol>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <div className="flex gap-2">
        <Button
          variant="primary"
          loading={busy}
          onClick={() => {
            setBusy(true);
            void onSave(order, [...hidden]).then((ok) => {
              setBusy(false);
              if (!ok) setError(fm(m.saveFailed));
            });
          }}
        >
          {fm(m.save)}
        </Button>
        <Button variant="secondary" onClick={onCancel}>
          {fm(m.cancel)}
        </Button>
      </div>
    </section>
  );
}

function ScopeSwitch({
  value,
  onChange,
}: {
  value: DashboardScope;
  onChange: (scope: DashboardScope) => void;
}) {
  const fm = useFormatMessage();
  const label = useId();
  const options: { value: DashboardScope; label: string }[] = [
    { value: "mine", label: fm(m.scopeMine) },
    { value: "all", label: fm(m.scopeAll) },
  ];
  return (
    <div role="group" aria-labelledby={label} className="flex items-center gap-2">
      <span id={label} className="text-sm text-fg-muted">
        {fm(m.scope)}
      </span>
      <div className="flex rounded-full border border-border p-0.5">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={value === option.value}
            className={`min-h-touch-target rounded-full px-3 text-sm font-semibold ${
              value === option.value ? "bg-surface-inverse text-fg-inverse" : "text-fg"
            }`}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function WidgetError({
  title,
  busy,
  onRetry,
}: {
  title: string;
  busy: boolean;
  onRetry: () => void;
}) {
  const fm = useFormatMessage();
  return (
    <div className="flex flex-col items-start gap-2" data-widget-error="">
      <p className="text-sm text-fg-danger">{fm(m.widgetFailed)}</p>
      <Button
        size="sm"
        variant="secondary"
        loading={busy}
        aria-label={fm(m.retryLabel, { title })}
        onClick={onRetry}
      >
        {fm(m.retry)}
      </Button>
    </div>
  );
}

function CountCard({
  practice,
  widget,
  busy,
  onRetry,
}: {
  practice: string;
  widget: DashboardWidget;
  busy: boolean;
  onRetry: () => void;
}) {
  const fm = useFormatMessage();
  const failed = widget.status === "error";
  const href = widget.filters
    ? practiceDirectoryFilteredUrl(practice, widget.filters)
    : widget.href || null;
  const linkText = widget.filters ? fm(m.openDirectory) : fm(m.openStaff);
  const linkLabel = widget.filters
    ? fm(m.openDirectoryLabel, { title: widget.title })
    : fm(m.openStaffLabel, { title: widget.title });
  return (
    <section
      className={`flex h-full flex-col gap-2 rounded-lg border p-4 ${
        failed ? "border-border-danger bg-surface-danger-subtle" : "border-border"
      }`}
      aria-label={widget.title}
      data-widget={widget.key}
      data-status={widget.status}
    >
      {failed ? (
        <>
          <h2 className="text-sm font-semibold text-fg">{widget.title}</h2>
          <WidgetError title={widget.title} busy={busy} onRetry={onRetry} />
        </>
      ) : (
        <>
          <p className="text-4xl font-bold text-fg tabular-nums" data-count="">
            {String(widget.count ?? 0)}
          </p>
          <h2 className="text-sm font-semibold text-fg">{widget.title}</h2>
          {widget.description ? (
            <p className="text-xs text-fg-muted">{widget.description}</p>
          ) : null}
          {href ? (
            <Link
              href={href}
              aria-label={linkLabel}
              className="mt-auto text-sm font-semibold text-fg-link underline"
            >
              {linkText}
            </Link>
          ) : null}
        </>
      )}
    </section>
  );
}

function ListPanel({
  widget,
  busy,
  onRetry,
}: {
  widget: DashboardWidget;
  busy: boolean;
  onRetry: () => void;
}) {
  const locale = useLocale() as AppLocale;
  const heading = useId();
  return (
    <section
      aria-labelledby={heading}
      className="flex flex-col gap-3 rounded-lg border border-border p-4"
      data-widget={widget.key}
      data-status={widget.status}
    >
      <div>
        <h2 id={heading} className="text-lg font-semibold text-fg">
          {widget.title}
        </h2>
        {widget.description ? <p className="text-xs text-fg-muted">{widget.description}</p> : null}
      </div>
      {widget.status === "error" ? (
        <WidgetError title={widget.title} busy={busy} onRetry={onRetry} />
      ) : widget.kind === "workload" ? (
        <Workload items={widget.items as unknown as WorkloadItem[]} />
      ) : (
        <Deadlines items={widget.items as unknown as DeadlineItem[]} locale={locale} />
      )}
    </section>
  );
}

function Deadlines({ items, locale }: { items: DeadlineItem[]; locale: AppLocale }) {
  const fm = useFormatMessage();
  if (items.length === 0) return <p className="text-sm text-fg-muted">{fm(m.deadlinesEmpty)}</p>;
  return (
    <ul className="flex flex-col divide-y divide-border text-sm" data-deadlines="">
      {items.map((item) => (
        <li
          key={`${item.date}-${item.kind}-${item.organisation_id}`}
          className="flex flex-wrap gap-x-4 py-2"
        >
          <time dateTime={item.date} className="w-24 font-semibold text-fg-muted">
            {formatDate(item.date, { locale })}
          </time>
          <span className="flex-1">{item.label}</span>
          <Link
            href={orgModuleUrl(item.organisation_id, "home")}
            className="text-fg-link underline"
          >
            {item.organisation_name}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Workload({ items }: { items: WorkloadItem[] }) {
  const fm = useFormatMessage();
  if (items.length === 0) return <p className="text-sm text-fg-muted">{fm(m.workloadEmpty)}</p>;
  const most = Math.max(1, ...items.map((item) => item.organisations));
  return (
    <ul className="flex flex-col gap-3 text-sm" data-workload="">
      {items.map((item) => (
        <li key={item.id} className="grid grid-cols-[10rem_1fr] items-center gap-3">
          <span className="truncate font-semibold">{item.name}</span>
          <span className="flex flex-col gap-1">
            <span
              aria-hidden="true"
              className="h-3 rounded-sm bg-surface-accent"
              style={{ width: `${Math.max(2, (100 * item.organisations) / most)}%` }}
            />
            <span className="text-xs text-fg-muted">
              {fm(m.workloadLine, { organisations: item.organisations, tasks: item.open_tasks })}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}
