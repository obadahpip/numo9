"use client";

/**
 * Out-of-cycle period (G-03a-T20, wireframe 67): dates and a note, then the overlap preview —
 * the server's result of adding it (`POST …/preview`, nothing written): unfiled periods it
 * overlaps removed or shortened, and the regular periods realigned from the day after it ends,
 * which the dialog says in words. An overlap with a filed period is refused with the period
 * named. "Add period" saves exactly the previewed result.
 */
import { Button, Dialog, Input } from "@numo9/ui";
import { formatDate, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useState } from "react";

import { useFormatMessage } from "@/i18n";

import { filingApi, nextDay, type CustomChange, type FilingDiff } from "./api";
import { DiffList } from "./DiffList";
import { fmsg } from "./messages";

export interface OutOfCycleDialogProps {
  org: string;
  registration: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (result: FilingDiff) => void;
}

export function OutOfCycleDialog({
  org,
  registration,
  open,
  onOpenChange,
  onSaved,
}: OutOfCycleDialogProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [note, setNote] = useState("");
  const [diff, setDiff] = useState<FilingDiff | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const change: CustomChange = { start, end, note: note.trim() };
  const valid = Boolean(start && end && end >= start);

  function edit(set: (value: string) => void, value: string) {
    set(value);
    setDiff(null); // the preview is of other dates now
    setError("");
  }

  function close(next: boolean) {
    if (!next) {
      setDiff(null);
      setError("");
    }
    onOpenChange(next);
  }

  async function preview() {
    if (!valid) {
      setError(fm(fmsg.customDates));
      return;
    }
    setBusy(true);
    setError("");
    const result = await filingApi.preview(org, registration, { action: "custom", ...change });
    setBusy(false);
    if (result.status === 200) setDiff(result.body);
    else {
      setDiff(null);
      setError(result.body?.detail || fm(fmsg.failed));
    }
  }

  async function save() {
    setBusy(true);
    const result = await filingApi.addCustom(org, registration, change);
    setBusy(false);
    if (result.status === 201) {
      onSaved(result.body);
      close(false);
      setStart("");
      setEnd("");
      setNote("");
    } else setError(result.body?.detail || fm(fmsg.failed));
  }

  return (
    <Dialog
      open={open}
      onOpenChange={close}
      title={fm(fmsg.customTitle)}
      description={fm(fmsg.customBody)}
      closeLabel={fm(fmsg.close)}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={() => close(false)}>
            {fm(fmsg.cancel)}
          </Button>
          {diff ? (
            <Button variant="primary" loading={busy} onClick={() => void save()}>
              {fm(fmsg.customSave)}
            </Button>
          ) : (
            <Button variant="primary" loading={busy} onClick={() => void preview()}>
              {fm(fmsg.previewButton)}
            </Button>
          )}
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1 text-sm font-medium text-fg">
            {fm(fmsg.customStart)}
            <Input
              type="date"
              value={start}
              onChange={(e) => edit(setStart, e.target.value)}
              required
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium text-fg">
            {fm(fmsg.customEnd)}
            <Input
              type="date"
              value={end}
              min={start || undefined}
              onChange={(e) => edit(setEnd, e.target.value)}
              required
            />
          </label>
        </div>
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(fmsg.customNote)}
          <Input value={note} onChange={(e) => edit(setNote, e.target.value)} />
        </label>
        {error ? (
          <p role="alert" className="text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
        {diff ? (
          <>
            <p role="status" data-check="ok" className="text-sm text-fg-success">
              {fm(fmsg.customOk)}
            </p>
            <p className="text-sm text-fg" data-realign="">
              {fm(fmsg.customRealign, { date: formatDate(nextDay(end), { locale }) })}
            </p>
            <DiffList diff={diff} />
          </>
        ) : null}
      </div>
    </Dialog>
  );
}
