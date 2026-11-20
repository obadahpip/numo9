"use client";

/**
 * Console → Founding offer (U-08-T11): the counter (x of 1,000 given, left), the churn and refund
 * rules, every founding place with its organisation, date, first payment and status, a CSV export
 * (one row per number given: the row count equals "given") and a confirmed release with a reason
 * (platform owners; recorded in the audit log, the number never given again).
 */
import { Badge, Button, Dialog, EmptyState, ErrorState, formatDate, Input } from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import {
  FOUNDING_EXPORT_URL,
  getFounding,
  releaseSlot,
  type FoundingOverview,
  type FoundingSlotRow,
} from "./api";
import { m } from "./messages";

const REASONS: Record<string, keyof typeof m> = {
  cancelled: "reasonCancelled",
  not_returned_in_time: "reasonNotReturned",
  refunded: "reasonRefunded",
  admin: "reasonAdmin",
};

export function foundingNumber(slot: number): string {
  return String(slot).padStart(4, "0");
}

export function FoundingScreen() {
  const fm = useFormatMessage();
  const [data, setData] = useState<FoundingOverview | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState("");

  useEffect(() => {
    let cancelled = false;
    void getFounding().then((result) => {
      if (cancelled) return;
      if (result.status === 200) {
        setData(result.body);
        setFailed(false);
      } else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

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

  const rule =
    data?.churn_rule === "keep_on_return"
      ? fm(m.ruleKeepOnReturn)
      : data?.churn_rule === "lose_on_cancel"
        ? fm(m.ruleLoseOnCancel)
        : fm(m.ruleWithinDays, { days: data?.return_window_days ?? 90 });

  return (
    <div className="flex flex-col gap-6" data-console-founding="">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex max-w-2xl flex-col gap-1">
          <h1 className="text-2xl font-bold text-fg">{fm(m.title)}</h1>
          <p className="text-sm text-fg-muted">{fm(m.intro, { cap: data?.cap ?? 1000 })}</p>
        </div>
        <a
          href={FOUNDING_EXPORT_URL}
          download
          className="inline-flex h-9 items-center rounded-md border border-border px-3 text-sm font-semibold text-fg hover:bg-surface-muted"
        >
          {fm(m.export)}
        </a>
      </div>
      <p role="status" className="sr-only">
        {status}
      </p>
      {data ? (
        <>
          <section
            aria-labelledby="founding-counter"
            className="flex flex-col gap-2 rounded-lg border border-border p-4"
          >
            <h2 id="founding-counter" className="text-lg font-semibold text-fg">
              {fm(m.counter, { allocated: data.allocated, cap: data.cap })}
            </h2>
            <div
              className="h-2 w-full overflow-hidden rounded-full bg-surface-muted"
              aria-hidden="true"
            >
              <div
                className="h-full rounded-full bg-surface-accent"
                style={{ width: `${data.cap ? (100 * data.allocated) / data.cap : 0}%` }}
              />
            </div>
            <p className="text-sm text-fg">
              {fm(m.summary, { remaining: data.remaining, active: data.active })}
            </p>
            <p className="text-sm text-fg-muted">{rule}</p>
            <p className="text-sm text-fg-muted">
              {fm(m.refundRule, { hours: data.refund_release_hours })}
            </p>
          </section>
          {data.slots.length === 0 ? (
            <EmptyState title={fm(m.empty)} body={fm(m.emptyBody)} compact />
          ) : (
            <SlotsTable
              slots={data.slots}
              onReleased={(row) => {
                setData((current) =>
                  current
                    ? {
                        ...current,
                        active: current.active - 1,
                        slots: current.slots.map((s) => (s.slot_no === row.slot_no ? row : s)),
                      }
                    : current,
                );
                setStatus(fm(m.released, { number: foundingNumber(row.slot_no) }));
              }}
            />
          )}
        </>
      ) : null}
    </div>
  );
}

function SlotsTable({
  slots,
  onReleased,
}: {
  slots: FoundingSlotRow[];
  onReleased: (row: FoundingSlotRow) => void;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as "en-CA" | "fr-CA";
  const stateLabel = (row: FoundingSlotRow) => {
    if (row.state === "active") return <Badge tone="success">{fm(m.stateActive)}</Badge>;
    if (row.state === "cancelled") return <Badge tone="warning">{fm(m.stateCancelled)}</Badge>;
    const key = REASONS[row.release_reason];
    return (
      <Badge tone="neutral">
        {fm(m.stateReleased, { reason: key ? fm(m[key]) : row.release_reason })}
      </Badge>
    );
  };
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-start text-sm">
        <caption className="sr-only">{fm(m.slotsCaption)}</caption>
        <thead>
          <tr className="border-b border-border text-fg-muted">
            <th scope="col" className="py-2 pe-3 text-start">
              {fm(m.number)}
            </th>
            <th scope="col" className="py-2 pe-3 text-start">
              {fm(m.organisation)}
            </th>
            <th scope="col" className="py-2 pe-3 text-start">
              {fm(m.allocatedAt)}
            </th>
            <th scope="col" className="py-2 pe-3 text-start">
              {fm(m.payment)}
            </th>
            <th scope="col" className="py-2 pe-3 text-start">
              {fm(m.state)}
            </th>
            <th scope="col" className="py-2 text-end">
              {fm(m.actions)}
            </th>
          </tr>
        </thead>
        <tbody>
          {slots.map((row) => (
            <tr key={row.slot_no} className="border-b border-border" data-slot={row.slot_no}>
              <td className="py-2 pe-3 font-mono tabular-nums">{foundingNumber(row.slot_no)}</td>
              <td className="py-2 pe-3">
                <Link
                  href={`/console/organisations/${row.organisation_id}`}
                  className="text-fg underline"
                >
                  {row.organisation_name}
                </Link>
              </td>
              <td className="py-2 pe-3">
                {formatDate(new Date(row.allocated_at), { locale, timeZone: "America/Toronto" })}
              </td>
              <td className="py-2 pe-3 font-mono text-xs">{row.payment_ref || fm(m.noPayment)}</td>
              <td className="py-2 pe-3">{stateLabel(row)}</td>
              <td className="py-2 text-end">
                {row.state === "released" ? null : (
                  <ReleaseButton row={row} onReleased={onReleased} />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReleaseButton({
  row,
  onReleased,
}: {
  row: FoundingSlotRow;
  onReleased: (row: FoundingSlotRow) => void;
}) {
  const fm = useFormatMessage();
  const ids = { reason: useId(), hint: useId(), error: useId() };
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const number = foundingNumber(row.slot_no);

  const submit = async () => {
    if (reason.trim().length < 5) {
      setError(fm(m.reasonTooShort));
      return;
    }
    setBusy(true);
    const result = await releaseSlot(row.slot_no, reason.trim());
    setBusy(false);
    if (result.status === 200 && "slot_no" in result.body) {
      setOpen(false);
      onReleased(result.body as FoundingSlotRow);
      return;
    }
    setError(result.status === 403 ? fm(m.forbidden) : fm(m.releaseFailed));
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) {
          setReason("");
          setError("");
        }
      }}
      trigger={
        <Button
          size="sm"
          variant="ghost"
          aria-label={fm(m.releaseLabel, { number, name: row.organisation_name })}
        >
          {fm(m.release)}
        </Button>
      }
      title={fm(m.releaseTitle, { number })}
      description={fm(m.releaseBody, { number, name: row.organisation_name })}
      closeLabel={fm(m.close)}
      size="sm"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setOpen(false)}>
            {fm(m.cancel)}
          </Button>
          <Button variant="danger" loading={busy} onClick={() => void submit()}>
            {fm(m.release)}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={ids.reason} className="text-sm font-semibold text-fg">
          {fm(m.reason)}
        </label>
        <Input
          id={ids.reason}
          value={reason}
          invalid={Boolean(error)}
          aria-describedby={error ? `${ids.hint} ${ids.error}` : ids.hint}
          onChange={(event) => {
            setReason(event.target.value);
            setError("");
          }}
        />
        <p id={ids.hint} className="text-xs text-fg-muted">
          {fm(m.reasonHint)}
        </p>
        {error ? (
          <p id={ids.error} role="alert" className="text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
      </div>
    </Dialog>
  );
}
