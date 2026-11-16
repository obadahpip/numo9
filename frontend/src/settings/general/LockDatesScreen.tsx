"use client";

import { Button, Dialog, ErrorState, Input, LoadingRegion, SkeletonTable } from "@numo9/ui";
import { useCallback, useEffect, useId, useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import type { FieldErrors } from "./api";
import {
  getImpact,
  getLockDates,
  setLockDate,
  type Impact,
  type Level,
  type LockRow,
} from "./lockDates";

const m = defineMessages({
  title: { id: "settings.locks.title", defaultMessage: "Lock dates", description: "Page heading" },
  intro: {
    id: "settings.locks.intro",
    defaultMessage:
      "Nothing dated on or before a lock date can be changed in that module. Advisers (your accountants) may still work in periods locked for everyone except advisers. The general ledger lock applies to every module.",
    description: "Text under the heading",
  },
  module: { id: "settings.locks.module", defaultMessage: "Module", description: "Column" },
  advisersOnly: {
    id: "settings.locks.advisersOnly",
    defaultMessage: "Everyone except advisers",
    description: "Column: lock level",
  },
  everyone: {
    id: "settings.locks.everyone",
    defaultMessage: "Everyone",
    description: "Column: lock level",
  },
  notLocked: {
    id: "settings.locks.notLocked",
    defaultMessage: "Not locked",
    description: "Empty cell",
  },
  change: {
    id: "settings.locks.change",
    defaultMessage: "{value} — {module}, {level}",
    description: "Accessible name of a cell's button (starts with its visible text)",
  },
  dialogTitle: {
    id: "settings.locks.dialogTitle",
    defaultMessage: "{module} — {level}",
    description: "Dialog title",
  },
  dialogBody: {
    id: "settings.locks.dialogBody",
    defaultMessage:
      "Changes dated on or before this date will be refused. Leave it empty to remove the lock.",
    description: "Dialog text",
  },
  date: { id: "settings.locks.date", defaultMessage: "Lock date", description: "Field" },
  reason: { id: "settings.locks.reason", defaultMessage: "Reason", description: "Field" },
  reasonHint: {
    id: "settings.locks.reasonHint",
    defaultMessage:
      "Required when the date moves back or the lock is removed: it reopens closed periods.",
    description: "Hint",
  },
  reasonNeeded: {
    id: "settings.locks.reasonNeeded",
    defaultMessage: "Moving the lock back reopens {date} and earlier: say why.",
    description: "Client-side error",
  },
  impactNone: {
    id: "settings.locks.impactNone",
    defaultMessage: "Nothing unposted is dated on or before {date}.",
    description: "Impact preview: nothing",
  },
  impactSome: {
    id: "settings.locks.impactSome",
    defaultMessage:
      "{count, plural, one {# record not posted is dated on or before {date}} other {# records not posted are dated on or before {date}}}: after locking, they can't be posted unless the lock moves back.",
    description: "Impact preview",
  },
  impactItem: {
    id: "settings.locks.impactItem",
    defaultMessage: "{label}: {count}",
    description: "Impact line",
  },
  checking: {
    id: "settings.locks.checking",
    defaultMessage: "Counting records not posted…",
    description: "Loading",
  },
  save: { id: "settings.locks.save", defaultMessage: "Save lock date", description: "Button" },
  cancel: { id: "settings.locks.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "settings.locks.close", defaultMessage: "Close", description: "Button" },
  saved: {
    id: "settings.locks.saved",
    defaultMessage: "{module} lock saved. The organisation's admins were told.",
    description: "Status",
  },
  failed: {
    id: "settings.locks.failed",
    defaultMessage: "The lock date couldn't be saved. Try again.",
    description: "Error",
  },
  loading: {
    id: "settings.locks.loading",
    defaultMessage: "Loading lock dates…",
    description: "Loading",
  },
  loadFailed: {
    id: "settings.locks.loadFailed",
    defaultMessage: "Lock dates couldn't be loaded",
    description: "Error",
  },
  loadFailedBody: {
    id: "settings.locks.loadFailedBody",
    defaultMessage: "Verify your connection, then try again.",
    description: "Error body",
  },
  retry: { id: "settings.locks.retry", defaultMessage: "Try again", description: "Retry" },
});

interface Editing {
  row: LockRow;
  level: Level;
}

/**
 * Settings → Lock dates (A-05-T13, flow F6): a matrix of modules × levels. Choosing a cell opens
 * a dialog with the date, the **impact preview** (records not posted dated on or before it,
 * A-05-T07, updated as the date changes) and the **reason** — required when the lock moves back
 * or is removed. Saving updates the matrix; the server's rules (levels out of order) show in the
 * dialog; the organisation's admins are notified.
 */
export function LockDatesScreen({ org }: Readonly<{ org: string }>) {
  const fm = useFormatMessage();
  const [rows, setRows] = useState<LockRow[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [status, setStatus] = useState("");

  const load = useCallback(async () => {
    setFailed(false);
    const answer = await getLockDates(org);
    if (answer.status === 200 && Array.isArray(answer.body)) setRows(answer.body);
    else setFailed(true);
  }, [org]);
  useEffect(() => {
    void load();
  }, [load]);

  const levelLabel = (level: Level) => fm(level === "everyone" ? m.everyone : m.advisersOnly);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex max-w-3xl flex-col gap-2">
        <h1 className="text-2xl font-semibold">{fm(m.title)}</h1>
        <p className="text-fg-muted">{fm(m.intro)}</p>
      </header>
      <p role="status" aria-live="polite" className="text-fg-muted" data-locks-status>
        {status}
      </p>
      {failed ? (
        <ErrorState
          title={fm(m.loadFailed)}
          body={fm(m.loadFailedBody)}
          retryLabel={fm(m.retry)}
          onRetry={() => void load()}
        />
      ) : rows === null ? (
        <LoadingRegion label={fm(m.loading)}>
          <SkeletonTable rows={6} columns={3} />
        </LoadingRegion>
      ) : (
        <table className="w-full max-w-3xl text-start">
          <thead>
            <tr className="border-b border-border text-sm text-fg-muted">
              <th scope="col" className="py-2 text-start font-medium">
                {fm(m.module)}
              </th>
              <th scope="col" className="py-2 text-start font-medium">
                {fm(m.advisersOnly)}
              </th>
              <th scope="col" className="py-2 text-start font-medium">
                {fm(m.everyone)}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.module} className="border-b border-border" data-lock-module={row.module}>
                <th scope="row" className="py-3 text-start font-normal">
                  {row.module_label}
                </th>
                {(["advisers_only", "everyone"] as const).map((level) => (
                  <td key={level} className="py-2" data-lock-level={level}>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditing({ row, level })}
                      aria-label={fm(m.change, {
                        value: row[level].date ?? fm(m.notLocked),
                        module: row.module_label,
                        level: levelLabel(level),
                      })}
                    >
                      {row[level].date ?? fm(m.notLocked)}
                    </Button>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing ? (
        <LockDialog
          org={org}
          editing={editing}
          levelLabel={levelLabel(editing.level)}
          onClose={() => setEditing(null)}
          onSaved={(matrix) => {
            setRows(matrix);
            setStatus(fm(m.saved, { module: editing.row.module_label }));
            setEditing(null);
          }}
        />
      ) : null}
    </div>
  );
}

function LockDialog({
  org,
  editing,
  levelLabel,
  onClose,
  onSaved,
}: Readonly<{
  org: string;
  editing: Editing;
  levelLabel: string;
  onClose: () => void;
  onSaved: (rows: LockRow[]) => void;
}>) {
  const fm = useFormatMessage();
  const id = useId();
  const current = editing.row[editing.level].date;
  const [date, setDate] = useState<string>(current ?? "");
  const [reason, setReason] = useState("");
  const [impact, setImpact] = useState<Impact | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [busy, setBusy] = useState(false);
  const movesBack = current !== null && (date === "" || date < current);

  useEffect(() => {
    setImpact(null);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return undefined;
    let alive = true;
    void getImpact(org, editing.row.module, date).then((answer) => {
      if (alive && answer.status === 200) setImpact(answer.body);
    });
    return () => {
      alive = false;
    };
  }, [org, editing.row.module, date]);

  const save = async () => {
    if (movesBack && !reason.trim()) {
      setErrors({ reason: [fm(m.reasonNeeded, { date: current ?? "" })] });
      return;
    }
    setBusy(true);
    const answer = await setLockDate(org, {
      module: editing.row.module,
      level: editing.level,
      date: date || null,
      reason: reason.trim(),
    });
    setBusy(false);
    if (answer.status === 200 && Array.isArray(answer.body)) onSaved(answer.body);
    else if (answer.status === 400) setErrors(answer.body as FieldErrors);
    else setErrors({ non_field_errors: [fm(m.failed)] });
  };

  const fieldError = (field: string) =>
    errors[field]?.[0] ? (
      <span id={`${id}-${field}-error`} className="text-sm text-fg-danger" role="alert">
        {errors[field]![0]}
      </span>
    ) : null;

  return (
    <Dialog
      open
      onOpenChange={(open) => (open ? null : onClose())}
      title={fm(m.dialogTitle, { module: editing.row.module_label, level: levelLabel })}
      description={fm(m.dialogBody)}
      closeLabel={fm(m.close)}
      footer={
        <>
          <Button onClick={onClose}>{fm(m.cancel)}</Button>
          <Button variant="primary" loading={busy} onClick={() => void save()}>
            {fm(m.save)}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-date`} className="font-medium">
            {fm(m.date)}
          </label>
          <Input
            id={`${id}-date`}
            type="date"
            value={date}
            onChange={(e) => {
              setDate(e.target.value);
              setErrors({});
            }}
            aria-describedby={errors.date ? `${id}-date-error` : undefined}
          />
          {fieldError("date")}
        </div>
        <div
          aria-live="polite"
          data-lock-impact
          className="rounded-md bg-surface-muted p-3 text-sm"
        >
          {date === "" ? null : impact === null ? (
            fm(m.checking)
          ) : impact.total === 0 ? (
            fm(m.impactNone, { date })
          ) : (
            <>
              <p>{fm(m.impactSome, { count: impact.total, date })}</p>
              <ul className="mt-1 list-disc ps-5">
                {impact.items
                  .filter((item) => item.count > 0)
                  .map((item) => (
                    <li key={`${item.module}-${item.kind}`}>
                      {fm(m.impactItem, { label: item.label, count: item.count })}
                    </li>
                  ))}
              </ul>
            </>
          )}
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-reason`} className="font-medium">
            {fm(m.reason)}
          </label>
          <span id={`${id}-reason-hint`} className="text-xs text-fg-muted">
            {fm(m.reasonHint)}
          </span>
          <Input
            id={`${id}-reason`}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            aria-describedby={`${id}-reason-hint${errors.reason ? ` ${id}-reason-error` : ""}`}
            aria-required={movesBack || undefined}
            invalid={Boolean(errors.reason)}
          />
          {fieldError("reason")}
        </div>
        {fieldError("non_field_errors")}
      </div>
    </Dialog>
  );
}
