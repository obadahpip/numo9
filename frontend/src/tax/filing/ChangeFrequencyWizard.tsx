"use client";

/**
 * Change filing frequency (G-03a-T19, wireframe 66): frequency → effective date → CRA approval
 * reference and date → preview. The preview is the server's own result of the change
 * (`POST …/preview`, nothing written): periods removed, added and shortened, with the warning
 * for a date that isn't a financial year start. A refusal (mid-year without the reference, a
 * date inside a filed period) is shown in words at the step it concerns. Confirm sends the same
 * change, so it saves exactly what was previewed.
 */
import { Button, Dialog, Input, RadioGroup } from "@numo9/ui";
import { useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { filingApi, type FilingDiff, type Frequency, type SwitchChange } from "./api";
import { DiffList } from "./DiffList";
import { fmsg, frequencyLabels } from "./messages";

const FREQUENCIES: Frequency[] = ["monthly", "quarterly", "annual"];
const STEPS = [fmsg.stepFrequency, fmsg.stepDate, fmsg.stepApproval, fmsg.stepPreview];

export interface ChangeFrequencyWizardProps {
  org: string;
  registration: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The frequency in force (preselects another one); none on a new registration. */
  current?: Frequency | null;
  /** Suggested effective date (the registration start when it has no frequency yet). */
  defaultDate?: string;
  onSaved: (result: FilingDiff) => void;
}

export function ChangeFrequencyWizard({
  org,
  registration,
  open,
  onOpenChange,
  current = null,
  defaultDate = "",
  onSaved,
}: ChangeFrequencyWizardProps) {
  const fm = useFormatMessage();
  const ids = useId();
  const [step, setStep] = useState(0);
  const [frequency, setFrequency] = useState<Frequency>(
    FREQUENCIES.find((f) => f !== current) ?? "quarterly",
  );
  const [effective, setEffective] = useState(defaultDate);
  const [ref, setRef] = useState("");
  const [approved, setApproved] = useState("");
  const [note, setNote] = useState("");
  const [diff, setDiff] = useState<FilingDiff | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const change: SwitchChange = {
    frequency,
    effective_from: effective,
    approval_ref: ref.trim(),
    approval_date: approved || null,
    note: note.trim(),
  };

  function close(next: boolean) {
    if (!next) {
      setStep(0);
      setDiff(null);
      setError("");
    }
    onOpenChange(next);
  }

  async function preview() {
    setBusy(true);
    setError("");
    const result = await filingApi.preview(org, registration, { action: "switch", ...change });
    setBusy(false);
    if (result.status === 200) {
      setDiff(result.body);
      setStep(3);
      return;
    }
    setDiff(null);
    setError(result.body?.detail || fm(fmsg.failed));
    // Send the person back to the step the refusal is about.
    const code = result.body?.code ?? "";
    setStep(code === "tax.filing.approval_required" ? 2 : 1);
  }

  async function confirm() {
    setBusy(true);
    setError("");
    const result = await filingApi.switchFrequency(org, registration, change);
    setBusy(false);
    if (result.status === 201) {
      onSaved(result.body);
      close(false);
    } else setError(result.body?.detail || fm(fmsg.failed));
  }

  const last = step === 3;
  return (
    <Dialog
      open={open}
      onOpenChange={close}
      title={fm(fmsg.wizardTitle)}
      description={fm(fmsg.wizardStep, {
        n: step + 1,
        total: STEPS.length,
        name: fm(STEPS[step]!),
      })}
      closeLabel={fm(fmsg.close)}
      size="lg"
      footer={
        <>
          <Button
            variant="secondary"
            onClick={() => (step === 0 ? close(false) : setStep(step - 1))}
          >
            {fm(step === 0 ? fmsg.cancel : fmsg.back)}
          </Button>
          {last ? (
            <Button variant="primary" loading={busy} onClick={() => void confirm()}>
              {fm(fmsg.confirm)}
            </Button>
          ) : step === 2 ? (
            <Button variant="primary" loading={busy} onClick={() => void preview()}>
              {fm(fmsg.previewButton)}
            </Button>
          ) : (
            <Button
              variant="primary"
              disabled={step === 1 && !effective}
              onClick={() => setStep(step + 1)}
            >
              {fm(fmsg.next)}
            </Button>
          )}
        </>
      }
    >
      <div className="flex flex-col gap-3" data-wizard-step={step + 1}>
        {error ? (
          <p role="alert" className="text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
        {step === 0 ? (
          <RadioGroup
            aria-label={fm(fmsg.frequencyLabel)}
            value={frequency}
            onValueChange={(value) => setFrequency(value as Frequency)}
            options={FREQUENCIES.map((f) => ({ value: f, label: fm(frequencyLabels[f]) }))}
          />
        ) : null}
        {step === 1 ? (
          <label
            htmlFor={`${ids}-date`}
            className="flex flex-col gap-1 text-sm font-medium text-fg"
          >
            {fm(fmsg.effectiveFrom)}
            <Input
              id={`${ids}-date`}
              type="date"
              value={effective}
              onChange={(e) => setEffective(e.target.value)}
              aria-describedby={`${ids}-date-help`}
              required
            />
            <span id={`${ids}-date-help`} className="font-normal text-fg-muted">
              {fm(fmsg.effectiveHelp)}
            </span>
          </label>
        ) : null}
        {step === 2 ? (
          <>
            <label
              htmlFor={`${ids}-ref`}
              className="flex flex-col gap-1 text-sm font-medium text-fg"
            >
              {fm(fmsg.approvalRef)}
              <Input
                id={`${ids}-ref`}
                value={ref}
                onChange={(e) => setRef(e.target.value)}
                maxLength={100}
                aria-describedby={`${ids}-ref-help`}
              />
              <span id={`${ids}-ref-help`} className="font-normal text-fg-muted">
                {fm(fmsg.approvalHelp)}
              </span>
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium text-fg">
              {fm(fmsg.approvalDate)}
              <Input type="date" value={approved} onChange={(e) => setApproved(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium text-fg">
              {fm(fmsg.note)}
              <Input value={note} onChange={(e) => setNote(e.target.value)} />
            </label>
          </>
        ) : null}
        {last && diff ? <DiffList diff={diff} /> : null}
      </div>
    </Dialog>
  );
}
