"use client";

/**
 * Start a support session (U-06-T11): the modal asks for the reason and the time limit
 * (15 minutes – 2 hours, default 30), then the browser opens the organisation as that user; the
 * red bar takes over from there.
 */
import { Button, Dialog } from "@numo9/ui";
import { useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { DEFAULT_DURATION, DURATIONS, impersonationLandingUrl, startImpersonation } from "./api";
import { m } from "./messages";

export interface StartImpersonationDialogProps {
  organisation: { id: string; name: string };
  user: { id: string; name: string };
  open: boolean;
  onClose: () => void;
  navigate?: (url: string) => void;
}

export function StartImpersonationDialog({
  organisation,
  user,
  open,
  onClose,
  navigate,
}: StartImpersonationDialogProps) {
  const fm = useFormatMessage();
  const [reason, setReason] = useState("");
  const [minutes, setMinutes] = useState<number>(DEFAULT_DURATION);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const ids = { reason: useId(), hint: useId(), error: useId(), duration: useId() };
  const go = navigate ?? ((url: string) => window.location.assign(url));

  const submit = async () => {
    setBusy(true);
    const result = await startImpersonation({
      organisation: organisation.id,
      user: user.id,
      reason,
      minutes,
    });
    setBusy(false);
    if (result.status === 201) {
      go(impersonationLandingUrl(organisation.id));
      return;
    }
    const body = result.body as { detail?: string } | undefined;
    setError(body?.detail ?? fm(m.failed));
  };

  const label = (value: number) =>
    value >= 60 ? fm(m.hours, { hours: value / 60 }) : fm(m.minutes, { minutes: value });

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => (next ? undefined : onClose())}
      title={fm(m.title, { name: user.name })}
      description={fm(m.description, { name: user.name, organisation: organisation.name })}
      closeLabel={fm(m.close)}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {fm(m.cancel)}
          </Button>
          <Button variant="danger" loading={busy} onClick={() => void submit()}>
            {fm(m.start)}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid gap-1">
          <label htmlFor={ids.reason} className="text-sm font-semibold">
            {fm(m.reason)}
          </label>
          <span id={ids.hint} className="text-xs text-fg-muted">
            {fm(m.reasonHint)}
          </span>
          <textarea
            id={ids.reason}
            required
            aria-describedby={error ? `${ids.hint} ${ids.error}` : ids.hint}
            aria-invalid={error ? true : undefined}
            className="min-h-24 rounded-md border border-border-strong bg-surface p-2 text-sm"
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          {error ? (
            <span id={ids.error} role="alert" className="text-sm text-fg-danger">
              {error}
            </span>
          ) : null}
        </div>
        <div className="grid gap-1">
          <label htmlFor={ids.duration} className="text-sm font-semibold">
            {fm(m.duration)}
          </label>
          <select
            id={ids.duration}
            className="min-h-touch-target rounded-md border border-border-strong bg-surface px-2 text-sm"
            value={minutes}
            onChange={(e) => setMinutes(Number(e.target.value))}
          >
            {DURATIONS.map((value) => (
              <option key={value} value={value}>
                {label(value)}
              </option>
            ))}
          </select>
        </div>
      </div>
    </Dialog>
  );
}
