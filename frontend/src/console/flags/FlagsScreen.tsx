"use client";

/**
 * Console → Feature flags (U-06-T12): every django-waffle flag with who it is on for — everyone,
 * nobody, or by rule (organisations, practices, a stable percentage of organisations) — a form to
 * create one and a confirmed delete. Each change is saved at once (and audited); the app reads the
 * result from `GET /api/v1/me/flags`.
 */
import { Button, CloseIcon, Dialog, EmptyState, ErrorState, Input } from "@numo9/ui";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import {
  createFlag,
  deleteFlag,
  listFlags,
  searchTargets,
  updateFlag,
  type ApiErrorBody,
  type FeatureFlag,
  type FlagMode,
  type FlagTarget,
  type FlagUpdate,
} from "./api";
import { m } from "./messages";

const MODES: FlagMode[] = ["on", "off", "rules"];

export function FlagsScreen() {
  const fm = useFormatMessage();
  const [flags, setFlags] = useState<FeatureFlag[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState("");

  useEffect(() => {
    let cancelled = false;
    void listFlags().then((result) => {
      if (cancelled) return;
      if (result.status === 200) {
        setFlags(result.body.flags);
        setFailed(false);
      } else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const replace = (flag: FeatureFlag) =>
    setFlags((current) => (current ?? []).map((row) => (row.name === flag.name ? flag : row)));

  if (failed) {
    return (
      <ErrorState
        title={fm(m.loadFailed)}
        retryLabel={fm(m.retry)}
        onRetry={() => setAttempt((n) => n + 1)}
        headingLevel={2}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6" data-console-flags="">
      <div>
        <h1 className="text-2xl font-bold text-fg">{fm(m.title)}</h1>
        <p className="text-sm text-fg-muted">{fm(m.intro)}</p>
      </div>
      <NewFlagForm
        onCreated={(flag) => {
          setFlags((current) =>
            [...(current ?? []), flag].sort((a, b) => a.name.localeCompare(b.name)),
          );
          setStatus(fm(m.saved, { name: flag.name }));
        }}
      />
      <p role="status" className="sr-only">
        {status}
      </p>
      {flags && flags.length === 0 ? <EmptyState title={fm(m.empty)} headingLevel={2} /> : null}
      <ul className="flex flex-col gap-4">
        {(flags ?? []).map((flag) => (
          <FlagCard
            key={flag.name}
            flag={flag}
            onSaved={(saved) => {
              replace(saved);
              setStatus(fm(m.saved, { name: saved.name }));
            }}
            onDeleted={() =>
              setFlags((current) => (current ?? []).filter((row) => row.name !== flag.name))
            }
          />
        ))}
      </ul>
    </div>
  );
}

function NewFlagForm({ onCreated }: { onCreated: (flag: FeatureFlag) => void }) {
  const fm = useFormatMessage();
  const ids = { name: useId(), hint: useId(), note: useId(), error: useId() };
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    const result = await createFlag(name, note);
    setBusy(false);
    if (result.status === 201) {
      setName("");
      setNote("");
      setError(null);
      onCreated(result.body as FeatureFlag);
    } else setError((result.body as ApiErrorBody | undefined)?.detail ?? fm(m.failed));
  };
  return (
    <section aria-labelledby={`${ids.name}-h`} className="rounded-lg border border-border p-4">
      <h2 id={`${ids.name}-h`} className="mb-3 text-lg font-semibold text-fg">
        {fm(m.newFlag)}
      </h2>
      <form
        className="flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <div className="grid gap-1">
          <label htmlFor={ids.name} className="text-sm font-semibold">
            {fm(m.name)}
          </label>
          <Input
            id={ids.name}
            value={name}
            maxLength={100}
            aria-describedby={error ? `${ids.hint} ${ids.error}` : ids.hint}
            aria-invalid={error ? true : undefined}
            onChange={(e) => setName(e.target.value)}
          />
          <span id={ids.hint} className="text-xs text-fg-muted">
            {fm(m.nameHint)}
          </span>
        </div>
        <div className="grid gap-1">
          <label htmlFor={ids.note} className="text-sm font-semibold">
            {fm(m.note)}
          </label>
          <Input id={ids.note} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>
        <Button type="submit" variant="primary" loading={busy}>
          {fm(m.create)}
        </Button>
        {error ? (
          <p id={ids.error} role="alert" className="w-full text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
      </form>
    </section>
  );
}

interface FlagCardProps {
  flag: FeatureFlag;
  onSaved: (flag: FeatureFlag) => void;
  onDeleted: () => void;
}

function FlagCard({ flag, onSaved, onDeleted }: FlagCardProps) {
  const fm = useFormatMessage();
  const ids = { mode: useId(), percent: useId(), error: useId() };
  const [percent, setPercent] = useState(flag.percent ?? "");
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  const save = async (update: FlagUpdate) => {
    const result = await updateFlag(flag.name, update);
    if (result.status === 200) {
      setError(null);
      onSaved(result.body as FeatureFlag);
    } else setError((result.body as ApiErrorBody | undefined)?.detail ?? fm(m.failed));
  };
  const modeLabel = { on: m.on, off: m.off, rules: m.rules };

  return (
    <li className="flex flex-col gap-3 rounded-lg border border-border p-4" data-flag={flag.name}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-mono text-base font-semibold text-fg">{flag.name}</h2>
        <Button size="sm" variant="ghost" onClick={() => setConfirming(true)}>
          {fm(m.delete)}
        </Button>
      </div>
      {flag.note ? <p className="text-sm text-fg-muted">{flag.note}</p> : null}
      <div className="flex flex-wrap items-center gap-2">
        <span id={ids.mode} className="text-sm font-semibold">
          {fm(m.mode)}
        </span>
        <div role="group" aria-labelledby={ids.mode} className="flex gap-1">
          {MODES.map((mode) => (
            <Button
              key={mode}
              size="sm"
              variant={flag.mode === mode ? "primary" : "secondary"}
              aria-pressed={flag.mode === mode}
              onClick={() => void save({ mode })}
            >
              {fm(modeLabel[mode])}
            </Button>
          ))}
        </div>
      </div>
      {flag.mode === "rules" ? (
        <div className="flex flex-col gap-3">
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void save({ percent: percent === "" ? null : percent });
            }}
          >
            <div className="grid gap-1">
              <label htmlFor={ids.percent} className="text-sm font-semibold">
                {fm(m.percent)}
              </label>
              <Input
                id={ids.percent}
                inputMode="decimal"
                className="w-28"
                value={percent}
                aria-describedby={error ? ids.error : undefined}
                onChange={(e) => setPercent(e.target.value)}
              />
            </div>
            <Button size="sm" type="submit">
              {fm(m.savePercent)}
            </Button>
          </form>
          <TargetList
            kind="organisations"
            title={fm(m.organisations)}
            addLabel={fm(m.addOrganisation)}
            items={flag.organisations}
            onChange={(items) => void save({ organisations: items.map((item) => item.id) })}
          />
          <TargetList
            kind="practices"
            title={fm(m.practices)}
            addLabel={fm(m.addPractice)}
            items={flag.practices}
            onChange={(items) => void save({ practices: items.map((item) => item.id) })}
          />
        </div>
      ) : null}
      {error ? (
        <p id={ids.error} role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <Dialog
        open={confirming}
        onOpenChange={setConfirming}
        title={fm(m.deleteTitle, { name: flag.name })}
        description={fm(m.deleteBody)}
        closeLabel={fm(m.close)}
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              {fm(m.cancel)}
            </Button>
            <Button
              variant="danger"
              onClick={() =>
                void deleteFlag(flag.name).then((result) => {
                  setConfirming(false);
                  if (result.status === 204) onDeleted();
                  else setError(fm(m.failed));
                })
              }
            >
              {fm(m.delete)}
            </Button>
          </div>
        }
      />
    </li>
  );
}

interface TargetListProps {
  kind: "organisations" | "practices";
  title: string;
  addLabel: string;
  items: FlagTarget[];
  onChange: (items: FlagTarget[]) => void;
}

function TargetList({ kind, title, addLabel, items, onChange }: TargetListProps) {
  const fm = useFormatMessage();
  const searchId = useId();
  const [q, setQ] = useState("");
  const [found, setFound] = useState<FlagTarget[]>([]);

  useEffect(() => {
    if (q.trim().length < 2) {
      setFound([]);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      void searchTargets(kind, q.trim()).then((result) => {
        if (!cancelled && result.status === 200) setFound(result.body.results);
      });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [kind, q]);

  const chosen = new Set(items.map((item) => item.id));
  return (
    <div className="flex flex-col gap-2" data-targets={kind}>
      <h3 className="text-sm font-semibold">{title}</h3>
      {items.length ? (
        <ul className="flex flex-wrap gap-2">
          {items.map((item) => (
            <li
              key={item.id}
              className="flex items-center gap-1 rounded-full border border-border px-2 text-sm"
            >
              {item.name}
              <Button
                size="sm"
                variant="ghost"
                aria-label={fm(m.remove, { name: item.name })}
                onClick={() => onChange(items.filter((other) => other.id !== item.id))}
              >
                <CloseIcon />
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-fg-muted">{fm(m.none)}</p>
      )}
      <div className="grid max-w-sm gap-1">
        <label htmlFor={searchId} className="text-xs font-semibold text-fg-muted">
          {addLabel}
        </label>
        <Input id={searchId} type="search" value={q} onChange={(e) => setQ(e.target.value)} />
        {found.filter((item) => !chosen.has(item.id)).length ? (
          <ul className="flex flex-col rounded-md border border-border">
            {found
              .filter((item) => !chosen.has(item.id))
              .map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    className="w-full px-2 py-1 text-start text-sm hover:bg-surface-muted"
                    aria-label={fm(m.add, { name: item.name })}
                    onClick={() => {
                      onChange([...items, { id: item.id, name: item.name }]);
                      setQ("");
                    }}
                  >
                    {item.name}
                  </button>
                </li>
              ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}
