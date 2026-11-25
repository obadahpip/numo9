"use client";

/**
 * Restart filing (G-03b-T10, wireframe 69): date (after the last day registered) and frequency →
 * the server's preview (the G-03a diff list; the gap stays "Not registered") → Restart, which
 * sends the same change and so saves exactly what was previewed.
 */
import { Button, Dialog, Input, Select } from "@numo9/ui";
import { useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { filingApi, type Frequency, type RegistrationStatus, type StopImpact } from "./api";
import { DiffList } from "./DiffList";
import { frequencyLabels } from "./messages";
import { smsg } from "./stopMessages";

const FREQUENCIES: Frequency[] = ["monthly", "quarterly", "annual"];

export interface RestartWizardProps {
  org: string;
  registration: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The last day registered (formatted), for the hint. */
  stopDate: string;
  onRestarted: (result: StopImpact & RegistrationStatus) => void;
}

export function RestartWizard({
  org,
  registration,
  open,
  onOpenChange,
  stopDate,
  onRestarted,
}: RestartWizardProps) {
  const fm = useFormatMessage();
  const ids = useId();
  const [date, setDate] = useState("");
  const [frequency, setFrequency] = useState<Frequency>("quarterly");
  const [impact, setImpact] = useState<StopImpact | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const change = { date, frequency };

  function close(next: boolean) {
    if (!next) {
      setImpact(null);
      setError("");
    }
    onOpenChange(next);
  }

  async function preview() {
    setBusy(true);
    setError("");
    const result = await filingApi.previewRestart(org, registration, change).catch(() => null);
    setBusy(false);
    if (result?.status === 200) setImpact(result.body);
    else setError(result?.body?.detail || fm(smsg.failed));
  }

  async function confirm() {
    setBusy(true);
    setError("");
    const result = await filingApi.restart(org, registration, change).catch(() => null);
    setBusy(false);
    if (result?.status === 201) {
      close(false);
      onRestarted(result.body);
    } else setError(result?.body?.detail || fm(smsg.failed));
  }

  return (
    <Dialog
      open={open}
      onOpenChange={close}
      title={fm(smsg.restartTitle)}
      closeLabel={fm(smsg.close)}
      footer={
        impact ? (
          <>
            <Button variant="secondary" onClick={() => setImpact(null)}>
              {fm(smsg.back)}
            </Button>
            <Button variant="primary" disabled={busy} onClick={() => void confirm()}>
              {fm(smsg.restartConfirm)}
            </Button>
          </>
        ) : (
          <>
            <Button variant="secondary" onClick={() => close(false)}>
              {fm(smsg.cancel)}
            </Button>
            <Button variant="primary" disabled={busy || !date} onClick={() => void preview()}>
              {fm(smsg.restartPreview)}
            </Button>
          </>
        )
      }
    >
      {impact ? (
        <DiffList diff={impact} />
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor={`${ids}-date`} className="text-sm font-medium text-fg">
              {fm(smsg.restartDate)}
            </label>
            <Input
              id={`${ids}-date`}
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
            <p className="text-xs text-fg-muted">{fm(smsg.restartHint, { date: stopDate })}</p>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${ids}-frequency`} className="text-sm font-medium text-fg">
              {fm(smsg.restartFrequency)}
            </label>
            <Select
              id={`${ids}-frequency`}
              value={frequency}
              onValueChange={(value) => setFrequency(value as Frequency)}
              options={FREQUENCIES.map((f) => ({ value: f, label: fm(frequencyLabels[f]) }))}
            />
          </div>
        </div>
      )}
      {error ? (
        <p role="alert" className="mt-2 text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
    </Dialog>
  );
}
