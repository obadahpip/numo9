"use client";

/**
 * Recurring journals (C-04-T11), `/o/:org/accounting/journals/recurring`: the templates (name,
 * schedule, next run, mode, paused) and the editor — name, narration, type, mode, the schedule
 * builder (every N weeks / months / quarters / years from a start date, optional end), the lines,
 * and the **next 6 dates** asked of the server (the generator the hourly job uses, so the preview
 * is what will happen). Pause and resume from the editor; the last runs show skipped dates with
 * the reason.
 */
import {
  AccountPicker,
  Badge,
  Button,
  EmptyState,
  ErrorState,
  formatDate,
  Input,
  type AppLocale,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useState, type FormEvent } from "react";

import { accountsApi, type Account } from "@/accounts/api";
import { pickerAccount } from "@/accounts/picker";
import { useDebounced } from "@/directory/useDebounced";
import { useDocumentLinesLabels } from "@/documents/labels";
import { useFormatMessage } from "@/i18n";

import type { JournalTypeKey } from "../write/api";
import { JournalTypePicker } from "../write/JournalTypePicker";
import {
  buildRule,
  readRule,
  recurringApi,
  type Frequency,
  type RecurringInput,
  type RecurringLine,
  type RecurringTemplate,
} from "./api";
import { rm } from "./messages";

export const PREVIEW_DEBOUNCE_MS = 300;
const PREVIEW_COUNT = 6;
const today = () => new Date().toISOString().slice(0, 10);
const emptyLine = (): RecurringLine => ({ account: "", debit: "", credit: "", description: "" });

interface Draft {
  name: string;
  narration: string;
  journalType: JournalTypeKey;
  mode: "draft" | "post";
  frequency: Frequency;
  every: number;
  start: string;
  end: string;
  lines: RecurringLine[];
}

const blank = (): Draft => ({
  name: "",
  narration: "",
  journalType: "general",
  mode: "draft",
  frequency: "monthly",
  every: 1,
  start: today(),
  end: "",
  lines: [emptyLine(), emptyLine()],
});

function fromTemplate(t: RecurringTemplate): Draft {
  const { frequency, every } = readRule(t.rrule);
  const amount = (v: string) => (Number(v) > 0 ? v : "");
  return {
    name: t.name,
    narration: t.narration,
    journalType: t.journal_type,
    mode: t.mode,
    frequency,
    every,
    start: t.start_date,
    end: t.end_date ?? "",
    lines: t.lines.map((l) => ({
      ...l,
      debit: amount(l.debit),
      credit: amount(l.credit),
      description: l.description ?? "",
    })),
  };
}

function toInput(d: Draft): RecurringInput {
  return {
    name: d.name.trim(),
    narration: d.narration,
    journal_type: d.journalType,
    mode: d.mode,
    rrule: buildRule(d.frequency, d.every),
    start_date: d.start,
    end_date: d.end || null,
    paused: false,
    lines: d.lines
      .filter((l) => l.account && (Number(l.debit) > 0 || Number(l.credit) > 0))
      .map((l) => ({
        account: l.account,
        debit: Number(l.debit) > 0 ? Number(l.debit).toFixed(2) : "0.00",
        credit: Number(l.credit) > 0 ? Number(l.credit).toFixed(2) : "0.00",
        description: l.description ?? "",
      })),
  };
}

function firstError(body: Record<string, unknown> | undefined): string | null {
  if (!body) return null;
  if (typeof body.detail === "string") return body.detail;
  for (const [key, value] of Object.entries(body)) {
    if (key !== "code" && Array.isArray(value) && typeof value[0] === "string") return value[0];
  }
  return null;
}

export function RecurringJournals({ org, initial }: Readonly<{ org: string; initial?: string }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [items, setItems] = useState<RecurringTemplate[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [editing, setEditing] = useState<string | "new" | null>(initial ?? null);

  const load = useCallback(
    () =>
      recurringApi
        .list(org)
        .then((r) => (r.status === 200 ? setItems(r.body.results) : setFailed(true)))
        .catch(() => setFailed(true)),
    [org],
  );
  useEffect(() => {
    void load();
  }, [load]);

  if (failed)
    return (
      <ErrorState
        title={fm(rm.loadFailed)}
        retryLabel={fm(rm.retry)}
        onRetry={() => {
          setFailed(false);
          void load();
        }}
      />
    );

  const schedule = (t: RecurringTemplate) => {
    const { frequency, every } = readRule(t.rrule);
    return fm(rm.every, { frequency, n: every });
  };

  return (
    <div className="flex flex-col gap-6 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-fg">{fm(rm.title)}</h1>
        <Button onClick={() => setEditing("new")}>{fm(rm.add)}</Button>
      </div>
      {items && items.length === 0 && editing === null ? (
        <EmptyState title={fm(rm.emptyTitle)} body={fm(rm.emptyBody)} />
      ) : null}
      {items && items.length > 0 ? (
        <table className="w-full text-sm" data-recurring-list="">
          <caption className="sr-only">{fm(rm.title)}</caption>
          <thead>
            <tr className="text-xs text-fg-muted">
              <th scope="col" className="py-1 text-start">
                {fm(rm.name)}
              </th>
              <th scope="col" className="py-1 text-start">
                {fm(rm.schedule)}
              </th>
              <th scope="col" className="py-1 text-start">
                {fm(rm.nextRun)}
              </th>
              <th scope="col" className="py-1 text-start">
                {fm(rm.mode)}
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.id} className="border-t border-border">
                <td className="flex flex-wrap items-center gap-2 py-2">
                  <button
                    type="button"
                    className="font-medium text-fg-link underline"
                    onClick={() => setEditing(t.id)}
                  >
                    {t.name}
                  </button>
                  {t.paused ? <Badge tone="warning">{fm(rm.paused)}</Badge> : null}
                </td>
                <td className="py-2">{schedule(t)}</td>
                <td className="py-2">
                  {t.next_run ? formatDate(t.next_run, { locale }) : fm(rm.finished)}
                </td>
                <td className="py-2">{fm(rm.modeName, { mode: t.mode })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {editing !== null ? (
        <RecurringEditor
          key={editing}
          org={org}
          id={editing === "new" ? null : editing}
          onSaved={(saved) => {
            setEditing(saved.id);
            void load();
          }}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </div>
  );
}

export function RecurringEditor({
  org,
  id,
  onSaved,
  onClose,
}: Readonly<{
  org: string;
  id: string | null;
  onSaved: (template: RecurringTemplate) => void;
  onClose: () => void;
}>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const { accountTypes, noAccounts } = useDocumentLinesLabels();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [template, setTemplate] = useState<RecurringTemplate | null>(null);
  const [draft, setDraft] = useState<Draft>(blank);
  const [dates, setDates] = useState<string[] | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void accountsApi.list(org, "active").then((r) => {
      if (r.status === 200) setAccounts(r.body.results.filter((a) => !a.has_children));
    });
  }, [org]);
  useEffect(() => {
    if (!id) return;
    void recurringApi.get(org, id).then((r) => {
      if (r.status !== 200) return;
      setTemplate(r.body);
      setDraft(fromTemplate(r.body));
    });
  }, [org, id]);

  const pickers = useMemo(() => accounts.map(pickerAccount), [accounts]);
  const set = (changes: Partial<Draft>) => setDraft((d) => ({ ...d, ...changes }));
  const setLine = (index: number, changes: Partial<RecurringLine>) =>
    set({ lines: draft.lines.map((l, i) => (i === index ? { ...l, ...changes } : l)) });

  const scheduleKey = useDebounced(
    JSON.stringify([buildRule(draft.frequency, draft.every), draft.start, draft.end]),
    PREVIEW_DEBOUNCE_MS,
  );
  useEffect(() => {
    const [rrule, start, end] = JSON.parse(scheduleKey) as [string, string, string];
    if (!start) return;
    let current = true;
    void recurringApi
      .preview(org, { rrule, start_date: start, end_date: end || null, count: PREVIEW_COUNT })
      .then((r) => {
        if (!current) return;
        if (r.status === 200) {
          setDates(r.body.dates);
          setPreviewError(null);
        } else {
          setDates(null);
          setPreviewError(firstError(r.body) ?? fm(rm.previewFailed));
        }
      })
      .catch(() => undefined);
    return () => {
      current = false;
    };
  }, [org, scheduleKey, fm]);

  const cents = (side: "debit" | "credit") =>
    draft.lines.reduce((sum, l) => sum + Math.round(Number(l[side] || 0) * 100), 0);
  const balanced = cents("debit") === cents("credit") && cents("debit") > 0;
  const ready = draft.name.trim().length > 0 && balanced;

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    const body = toInput(draft);
    const result = id
      ? await recurringApi.update(org, id, { ...body, paused: template?.paused ?? false })
      : await recurringApi.create(org, body);
    setBusy(false);
    if (result.status === 200 || result.status === 201) {
      setTemplate(result.body);
      onSaved(result.body);
    } else {
      setError(firstError(result.body) ?? fm(rm.saveFailed));
    }
  };

  const togglePause = async () => {
    if (!id || !template) return;
    setBusy(true);
    const result = await recurringApi.update(org, id, { paused: !template.paused });
    setBusy(false);
    if (result.status === 200) {
      setTemplate(result.body);
      onSaved(result.body);
    }
  };

  return (
    <form
      aria-labelledby={`${ids}-title`}
      onSubmit={(event) => void save(event)}
      className="flex flex-col gap-5 rounded-md border border-border p-4"
      data-recurring-editor=""
      noValidate
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={`${ids}-title`} className="text-lg font-semibold text-fg">
          {id ? fm(rm.editTitle, { name: template?.name ?? "" }) : fm(rm.newTitle)}
        </h2>
        {template?.paused ? <Badge tone="warning">{fm(rm.paused)}</Badge> : null}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(rm.name)}
          <Input value={draft.name} onChange={(e) => set({ name: e.target.value })} required />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(rm.narration)}
          <Input value={draft.narration} onChange={(e) => set({ narration: e.target.value })} />
        </label>
      </div>
      <JournalTypePicker
        value={draft.journalType}
        onChange={(journalType) => set({ journalType })}
      />

      <fieldset className="flex flex-col gap-3" data-schedule="">
        <legend className="text-sm font-semibold text-fg">{fm(rm.schedule)}</legend>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium text-fg">
            {fm(rm.repeatEvery)}
            <Input
              type="number"
              min={1}
              max={99}
              className="w-20"
              value={String(draft.every)}
              onChange={(e) => set({ every: Number(e.target.value) || 1 })}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-fg">
            {fm(rm.unit)}
            <select
              value={draft.frequency}
              onChange={(e) => set({ frequency: e.target.value as Frequency })}
              className="min-h-touch-target rounded-md border border-border bg-surface px-2 text-sm text-fg"
            >
              {(["weekly", "monthly", "quarterly", "yearly"] as const).map((f) => (
                <option key={f} value={f}>
                  {fm(rm.unitName, { frequency: f })}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-fg">
            {fm(rm.start)}
            <Input
              type="date"
              value={draft.start}
              onChange={(e) => set({ start: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-fg">
            {fm(rm.end)}
            <Input type="date" value={draft.end} onChange={(e) => set({ end: e.target.value })} />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-fg">
            {fm(rm.mode)}
            <select
              value={draft.mode}
              onChange={(e) => set({ mode: e.target.value as "draft" | "post" })}
              className="min-h-touch-target rounded-md border border-border bg-surface px-2 text-sm text-fg"
            >
              <option value="draft">{fm(rm.modeName, { mode: "draft" })}</option>
              <option value="post">{fm(rm.modeName, { mode: "post" })}</option>
            </select>
          </label>
        </div>
        <section aria-labelledby={`${ids}-preview`} data-preview="">
          <h3 id={`${ids}-preview`} className="text-sm font-semibold text-fg">
            {fm(rm.nextDates, { count: PREVIEW_COUNT })}
          </h3>
          {previewError ? (
            <p role="alert" className="text-sm text-fg-danger">
              {previewError}
            </p>
          ) : dates && dates.length === 0 ? (
            <p className="text-sm text-fg-muted">{fm(rm.noDates)}</p>
          ) : (
            <ol className="mt-1 flex flex-wrap gap-2 text-sm" aria-live="polite">
              {(dates ?? []).map((day) => (
                <li
                  key={day}
                  data-date={day}
                  className="rounded-full bg-surface-muted px-3 py-1 tabular-nums"
                >
                  {formatDate(day, { locale })}
                </li>
              ))}
            </ol>
          )}
        </section>
      </fieldset>

      <table className="w-full text-sm">
        <caption className="pb-2 text-start text-sm font-semibold text-fg">{fm(rm.lines)}</caption>
        <thead>
          <tr className="text-xs text-fg-muted">
            <th scope="col" className="w-2/5 py-1 text-start">
              {fm(rm.account)}
            </th>
            <th scope="col" className="py-1 text-end">
              {fm(rm.debit)}
            </th>
            <th scope="col" className="py-1 text-end">
              {fm(rm.credit)}
            </th>
            <th scope="col" className="py-1 text-start">
              {fm(rm.description)}
            </th>
          </tr>
        </thead>
        <tbody>
          {draft.lines.map((line, index) => {
            const n = index + 1;
            return (
              <tr key={index} className="border-t border-border align-top">
                <td className="py-2 pe-2">
                  <AccountPicker
                    aria-label={fm(rm.accountOfLine, { line: n })}
                    accounts={pickers}
                    context="journal"
                    value={line.account || null}
                    onChange={(account) => setLine(index, { account: account ?? "" })}
                    typeLabels={accountTypes}
                    emptyMessage={noAccounts}
                  />
                </td>
                <td className="py-2 pe-2">
                  <Input
                    numeric
                    inputMode="decimal"
                    aria-label={fm(rm.debitOfLine, { line: n })}
                    value={line.debit}
                    onChange={(e) => setLine(index, { debit: e.target.value, credit: "" })}
                  />
                </td>
                <td className="py-2 pe-2">
                  <Input
                    numeric
                    inputMode="decimal"
                    aria-label={fm(rm.creditOfLine, { line: n })}
                    value={line.credit}
                    onChange={(e) => setLine(index, { credit: e.target.value, debit: "" })}
                  />
                </td>
                <td className="py-2">
                  <Input
                    aria-label={fm(rm.descriptionOfLine, { line: n })}
                    value={line.description ?? ""}
                    onChange={(e) => setLine(index, { description: e.target.value })}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button
          variant="secondary"
          type="button"
          onClick={() => set({ lines: [...draft.lines, emptyLine()] })}
        >
          {fm(rm.addLine)}
        </Button>
        <p role="status" className="text-sm text-fg-muted" data-balanced={balanced}>
          {balanced
            ? fm(rm.balanced)
            : fm(rm.outOfBalance, {
                amount: (Math.abs(cents("debit") - cents("credit")) / 100).toFixed(2),
              })}
        </p>
      </div>

      {template?.runs?.length ? (
        <section aria-labelledby={`${ids}-runs`}>
          <h3 id={`${ids}-runs`} className="text-sm font-semibold text-fg">
            {fm(rm.lastRuns)}
          </h3>
          <ul className="mt-1 text-sm">
            {template.runs.map((run) => (
              <li key={run.date} data-run={run.status}>
                {fm(run.status === "skipped" ? rm.skippedOn : rm.createdOn, {
                  date: formatDate(run.date, { locale }),
                  reason: run.message,
                })}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={busy || !ready}>
          {fm(rm.save)}
        </Button>
        {id && template ? (
          <Button
            variant="secondary"
            type="button"
            disabled={busy}
            onClick={() => void togglePause()}
          >
            {template.paused ? fm(rm.resume) : fm(rm.pause)}
          </Button>
        ) : null}
        <Button variant="ghost" type="button" onClick={onClose}>
          {fm(rm.close)}
        </Button>
      </div>
    </form>
  );
}
