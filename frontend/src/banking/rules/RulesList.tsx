"use client";

/**
 * Bank rules list (F-04-T10): one tab per rule type (spend / receive / transfer), the rules in
 * priority order — the first match wins — with a **drag handle** (dnd-kit: pointer, touch, and
 * keyboard: Space, arrows, Space) that renumbers them through the atomic reorder endpoint, an
 * **on/off switch**, the "applied N times · last …" counter, an auto-apply badge, the disabled
 * warning (archived account) and a **search** over names and condition values (reordering is
 * off while searching). A failed reorder puts the previous order back.
 */
import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Badge,
  EmptyState,
  ErrorState,
  Input,
  Skeleton,
  Switch,
  formatDate,
  type AppLocale,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { RULE_TYPES, rulesApi, ruleUrl, type BankRule, type RuleType } from "./api";
import { describeConditions } from "./describe";
import { m, typeLabels } from "./messages";

const TIME_ZONE = "America/Toronto";

export interface RulesListProps {
  org: string;
  initialType?: RuleType;
}

function matches(rule: BankRule, search: string): boolean {
  const wanted = search.trim().toLocaleLowerCase();
  if (!wanted) return true;
  return (
    rule.name.toLocaleLowerCase().includes(wanted) ||
    rule.conditions.some((c) => c.value.toLocaleLowerCase().includes(wanted))
  );
}

export function RulesList({ org, initialType = "spend" }: RulesListProps) {
  const fm = useFormatMessage();
  const [type, setType] = useState<RuleType>(initialType);
  const [rules, setRules] = useState<BankRule[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    setRules(null);
    void rulesApi
      .list(org, { type })
      .then((result) => {
        if (cancelled) return;
        if (result.status === 200 && Array.isArray(result.body?.results)) {
          setRules(result.body.results);
        } else setFailed(true);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, [org, type, attempt]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const searching = search.trim() !== "";
  const shown = useMemo(() => (rules ?? []).filter((r) => matches(r, search)), [rules, search]);

  async function onDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!rules || !over || active.id === over.id) return;
    const before = rules;
    const from = rules.findIndex((r) => r.id === active.id);
    const to = rules.findIndex((r) => r.id === over.id);
    if (from < 0 || to < 0) return;
    const moved = arrayMove(rules, from, to).map((r, index) => ({ ...r, priority: index + 1 }));
    setRules(moved);
    setError("");
    const result = await rulesApi
      .reorder(
        org,
        type,
        moved.map((r) => r.id),
      )
      .catch(() => null);
    if (result?.status === 200 && Array.isArray(result.body.results)) {
      setRules(result.body.results);
      const rule = moved[to]!;
      setStatus(fm(m.moved, { name: rule.name, priority: to + 1 }));
    } else {
      setRules(before);
      setError(fm(m.reorderFailed));
    }
  }

  async function toggle(rule: BankRule, active: boolean) {
    setRules((current) => current?.map((r) => (r.id === rule.id ? { ...r, active } : r)) ?? null);
    const result = await rulesApi.update(org, rule.id, { active }).catch(() => null);
    if (result?.status !== 200) {
      setRules(
        (current) =>
          current?.map((r) => (r.id === rule.id ? { ...r, active: rule.active } : r)) ?? null,
      );
      setError(fm(m.toggleFailed, { name: rule.name }));
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex max-w-3xl flex-col gap-1">
          <h1 className="text-2xl font-bold text-fg">{fm(m.title)}</h1>
          <p className="text-sm text-fg-muted">{fm(m.intro)}</p>
        </div>
        <Link
          href={`${ruleUrl(org)}?type=${type}`}
          className="inline-flex min-h-touch-target items-center rounded-md bg-surface-inverse px-4 text-sm font-semibold text-fg-inverse"
        >
          {fm(m.newRule)}
        </Link>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div role="group" aria-label={fm(m.typeTabs)} className="flex gap-2">
          {RULE_TYPES.map((t) => (
            <button
              key={t}
              type="button"
              aria-pressed={t === type}
              onClick={() => setType(t)}
              className="min-h-touch-target rounded-md border border-border px-3 text-sm font-semibold text-fg aria-pressed:bg-surface-inverse aria-pressed:text-fg-inverse"
            >
              {fm(typeLabels[t])}
            </button>
          ))}
        </div>
        <label className="flex flex-col gap-1 text-sm font-semibold text-fg">
          {fm(m.search)}
          <Input type="search" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
      </div>

      <p role="status" className="sr-only">
        {status}
      </p>
      {error ? (
        <p role="alert" className="text-sm font-semibold text-fg-danger">
          {error}
        </p>
      ) : null}
      {searching ? <p className="text-sm text-fg-muted">{fm(m.searchHint)}</p> : null}

      {failed ? (
        <ErrorState
          title={fm(m.loadFailed)}
          body={fm(m.loadFailedBody)}
          retryLabel={fm(m.retry)}
          onRetry={() => setAttempt((n) => n + 1)}
          headingLevel={2}
        />
      ) : rules === null ? (
        <div aria-busy="true" className="flex flex-col gap-2">
          <span className="sr-only">{fm(m.loading)}</span>
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      ) : rules.length === 0 ? (
        <EmptyState
          title={fm(m.emptyTitle)}
          body={fm(m.emptyBody)}
          headingLevel={2}
          actions={[
            <Link
              key="new"
              href={`${ruleUrl(org)}?type=${type}`}
              className="font-semibold underline"
            >
              {fm(m.newRule)}
            </Link>,
          ]}
        />
      ) : shown.length === 0 ? (
        <p className="text-sm text-fg-muted">{fm(m.noMatch, { search })}</p>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={(event) => void onDragEnd(event)}
          accessibility={{ screenReaderInstructions: { draggable: fm(m.dragInstructions) } }}
        >
          <SortableContext items={shown.map((r) => r.id)} strategy={verticalListSortingStrategy}>
            <ol className="flex flex-col gap-2" aria-label={fm(typeLabels[type])}>
              {shown.map((rule) => (
                <RuleRow
                  key={rule.id}
                  org={org}
                  rule={rule}
                  sortable={!searching}
                  onToggle={(active) => void toggle(rule, active)}
                />
              ))}
            </ol>
          </SortableContext>
        </DndContext>
      )}
    </div>
  );
}

function RuleRow({
  org,
  rule,
  sortable,
  onToggle,
}: {
  org: string;
  rule: BankRule;
  sortable: boolean;
  onToggle: (active: boolean) => void;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: rule.id,
    disabled: !sortable,
  });
  const style = { transform: CSS.Transform.toString(transform), transition };
  const counter = rule.last_applied_at
    ? fm(m.applied, {
        count: rule.applied_count,
        date: formatDate(new Date(rule.last_applied_at), { locale, timeZone: TIME_ZONE }),
      })
    : fm(m.neverApplied);
  return (
    <li
      ref={setNodeRef}
      style={style}
      data-rule={rule.id}
      aria-label={rule.name}
      className={`flex items-center gap-3 rounded-lg border border-border bg-surface p-3 ${
        isDragging ? "shadow-elevation-2" : ""
      }`}
    >
      <button
        type="button"
        className="flex size-touch-target shrink-0 cursor-grab items-center justify-center rounded-md text-fg-muted disabled:cursor-not-allowed disabled:opacity-40"
        aria-label={fm(m.dragHandle, { name: rule.name })}
        disabled={!sortable}
        {...attributes}
        {...listeners}
      >
        <svg aria-hidden="true" viewBox="0 0 20 20" className="size-5" fill="currentColor">
          <circle cx="7" cy="5" r="1.5" />
          <circle cx="13" cy="5" r="1.5" />
          <circle cx="7" cy="10" r="1.5" />
          <circle cx="13" cy="10" r="1.5" />
          <circle cx="7" cy="15" r="1.5" />
          <circle cx="13" cy="15" r="1.5" />
        </svg>
      </button>
      <span className="w-8 shrink-0 text-center text-sm font-semibold tabular-nums text-fg-muted">
        <span className="sr-only">{fm(m.priority, { priority: rule.priority ?? "" })}</span>
        <span aria-hidden="true">{rule.priority}</span>
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={ruleUrl(org, rule.id)}
            className="font-semibold text-fg underline-offset-2 hover:underline"
          >
            {rule.name}
          </Link>
          {rule.auto_apply ? <Badge tone="info">{fm(m.autoApply)}</Badge> : null}
          {!rule.active ? <Badge tone="neutral">{fm(m.off)}</Badge> : null}
        </div>
        <p className="truncate text-sm text-fg-muted">
          {describeConditions(fm, rule.conditions, rule.match_mode)}
        </p>
        <p className="text-xs text-fg-muted" data-counter="">
          {counter}
        </p>
        {rule.warnings.length ? (
          <p className="text-xs font-semibold text-fg-warning">{fm(m.disabledWarning)}</p>
        ) : null}
      </div>
      <Switch
        checked={rule.active}
        onCheckedChange={onToggle}
        aria-label={fm(m.toggle, { name: rule.name })}
      />
    </li>
  );
}
