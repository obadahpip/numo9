"use client";

/**
 * Stop filing — the danger zone (G-03b-T10, wireframe 68): last day registered, reason and note;
 * "Review the impact" shows the server's preview (the same result as saving: the final return,
 * the periods removed, the documents dated after the stop that use the registration's tax codes,
 * the out-of-scope default). **Stop filing** stays disabled until the registration number is
 * typed exactly (letters and digits; spaces ignored); the server checks it again.
 */
import { Button, Input, Select, formatDate, type AppLocale } from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import {
  bareNumber,
  filingApi,
  type RegistrationStatus,
  type StopImpact,
  type StopReason,
} from "./api";
import { DiffList } from "./DiffList";
import { reasonLabels, smsg } from "./stopMessages";

const REASONS: StopReason[] = ["deregistration", "small_supplier", "suspension", "other"];

export interface StopFilingCardProps {
  org: string;
  registration: string;
  /** The registration number, as stored (the one to type). */
  number: string;
  onStopped: (result: StopImpact & RegistrationStatus) => void;
}

export function StopFilingCard({ org, registration, number, onStopped }: StopFilingCardProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [date, setDate] = useState("");
  const [reason, setReason] = useState<StopReason>("deregistration");
  const [note, setNote] = useState("");
  const [impact, setImpact] = useState<StopImpact | null>(null);
  const [typed, setTyped] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const day = (value: string) => formatDate(value, { locale });
  const change = { date, reason_code: reason, reason_text: note.trim() };
  const matches = bareNumber(typed) === bareNumber(number) && typed.trim() !== "";

  function edited() {
    setImpact(null);
    setError("");
  }

  async function review() {
    setBusy(true);
    setError("");
    const result = await filingApi.previewStop(org, registration, change).catch(() => null);
    setBusy(false);
    if (result?.status === 200) setImpact(result.body);
    else setError(result?.body?.detail || fm(smsg.failed));
  }

  async function confirm() {
    setBusy(true);
    setError("");
    const result = await filingApi
      .stop(org, registration, { ...change, confirm_number: typed })
      .catch(() => null);
    setBusy(false);
    if (result?.status === 201) onStopped(result.body);
    else setError(result?.body?.detail || fm(smsg.failed));
  }

  const final = impact?.periods.length ? impact.periods[impact.periods.length - 1] : null;
  return (
    <section
      aria-labelledby={`${ids}-title`}
      className="flex flex-col gap-3 rounded-md border border-fg-danger p-4"
      data-danger-zone=""
    >
      <h2 id={`${ids}-title`} className="text-lg font-semibold text-fg-danger">
        {fm(smsg.dangerTitle)}
      </h2>
      <p className="text-sm text-fg">{fm(smsg.dangerIntro)}</p>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="flex flex-col gap-1">
          <label htmlFor={`${ids}-date`} className="text-sm font-medium text-fg">
            {fm(smsg.lastDay)}
          </label>
          <Input
            id={`${ids}-date`}
            type="date"
            value={date}
            onChange={(e) => {
              setDate(e.target.value);
              edited();
            }}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${ids}-reason`} className="text-sm font-medium text-fg">
            {fm(smsg.reason)}
          </label>
          <Select
            id={`${ids}-reason`}
            value={reason}
            onValueChange={(value) => {
              setReason(value as StopReason);
              edited();
            }}
            options={REASONS.map((r) => ({ value: r, label: fm(reasonLabels[r]) }))}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${ids}-note`} className="text-sm font-medium text-fg">
            {fm(smsg.note)}
          </label>
          <Input
            id={`${ids}-note`}
            value={note}
            onChange={(e) => {
              setNote(e.target.value);
              edited();
            }}
          />
        </div>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      {!impact ? (
        <div>
          <Button variant="secondary" disabled={busy || !date} onClick={() => void review()}>
            {fm(smsg.reviewImpact)}
          </Button>
        </div>
      ) : (
        <>
          <div
            className="flex flex-col gap-1 rounded-md bg-surface-danger-subtle p-3 text-sm text-fg"
            data-impact=""
          >
            <h3 className="font-semibold">{fm(smsg.impactTitle)}</h3>
            {final ? (
              <p>{fm(smsg.impactFinal, { start: day(final.start), end: day(final.end) })}</p>
            ) : null}
            <p>{fm(smsg.impactRemoved, { count: impact.removed.length, date: day(date) })}</p>
            {impact.documents.length ? (
              <div data-post-stop="">
                <p className="font-medium text-fg-danger">
                  {fm(smsg.impactDocuments, { count: impact.documents.length, date: day(date) })}
                </p>
                <ul className="list-disc pl-5">
                  {impact.documents.map((doc) => (
                    <li key={doc.id}>
                      <Link href={doc.url} className="underline">
                        {fm(smsg.documentLink, {
                          number: doc.number || fm(smsg.draft),
                          date: day(doc.date),
                        })}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {impact.out_of_scope_default ? (
              <p>{fm(smsg.impactOutOfScope, { date: day(date) })}</p>
            ) : null}
          </div>
          <DiffList diff={impact} />
          <div className="flex flex-col gap-1">
            <label htmlFor={`${ids}-confirm`} className="text-sm font-medium text-fg">
              {fm(smsg.confirmLabel, { number })}
            </label>
            <Input
              id={`${ids}-confirm`}
              value={typed}
              autoComplete="off"
              onChange={(e) => setTyped(e.target.value)}
              className="max-w-sm"
            />
            <p className="text-xs text-fg-muted">{fm(smsg.confirmHint)}</p>
          </div>
          <div className="flex gap-2">
            <Button variant="danger" disabled={busy || !matches} onClick={() => void confirm()}>
              {fm(smsg.confirmButton)}
            </Button>
            <Button variant="secondary" onClick={edited}>
              {fm(smsg.cancel)}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
