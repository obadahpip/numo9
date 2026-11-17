"use client";

/**
 * Progress drawer + results (V-03-T10): while the job runs the drawer asks for its status every
 * second — the counters (succeeded, skipped, failed, waiting) and the progress bar move live —
 * with *Cancel the rest*. When it ends: the results, one line per organisation with its outcome
 * and reason, filterable by outcome, and the results CSV (and the export file for an export).
 * Closing the drawer doesn't stop the job (it is also in the job tray, A-08).
 */
import { Button, Drawer } from "@numo9/ui";
import { useEffect, useState } from "react";

import { useFormatMessage, type MessageDescriptor } from "@/i18n";

import {
  bulkApi,
  exportUrl,
  resultsCsvUrl,
  type BulkJob,
  type BulkRowPage,
  type RowOutcome,
} from "./api";
import { m } from "./messages";

export const POLL_MS = 1000;
const FINISHED = new Set(["completed", "cancelled"]);
const FILTERS: ("" | RowOutcome)[] = ["", "succeeded", "skipped", "failed", "cancelled"];

export interface BulkProgressDrawerProps {
  job: BulkJob;
  onClose: () => void;
  /** Called once when the job ends (the directory refreshes). */
  onFinished?: (job: BulkJob) => void;
}

export function BulkProgressDrawer({ job: initial, onClose, onFinished }: BulkProgressDrawerProps) {
  const fm = useFormatMessage();
  const [job, setJob] = useState<BulkJob>(initial);
  const [outcome, setOutcome] = useState<"" | RowOutcome>("");
  const [rows, setRows] = useState<BulkRowPage | null>(null);
  const finished = FINISHED.has(job.status);

  useEffect(() => {
    if (finished) return;
    let cancelled = false;
    const timer = setInterval(() => {
      void bulkApi.get(job.id).then((result) => {
        if (cancelled || result.status !== 200) return;
        setJob(result.body);
        if (FINISHED.has(result.body.status)) onFinished?.(result.body);
      });
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [job.id, finished, onFinished]);

  useEffect(() => {
    if (!finished) return;
    let cancelled = false;
    void bulkApi.rows(job.id, outcome).then((result) => {
      if (!cancelled && result.status === 200) setRows(result.body);
    });
    return () => {
      cancelled = true;
    };
  }, [job.id, finished, outcome]);

  const statusLabel: Record<string, MessageDescriptor> = {
    preview: m.statusQueued,
    queued: m.statusQueued,
    running: m.statusRunning,
    completed: m.statusCompleted,
    cancelled: m.statusCancelled,
  };
  const counters: [string, MessageDescriptor, number][] = [
    ["succeeded", m.countSucceeded, job.counts.succeeded],
    ["skipped", m.countSkipped, job.counts.skipped],
    ["failed", m.countFailed, job.counts.failed],
    finished
      ? ["cancelled", m.countCancelled, job.counts.cancelled]
      : ["pending", m.countWaiting, job.counts.pending],
  ];
  const outcomeLabel: Record<RowOutcome, MessageDescriptor> = {
    pending: m.countWaiting,
    succeeded: m.countSucceeded,
    skipped: m.countSkipped,
    failed: m.countFailed,
    cancelled: m.countCancelled,
  };

  return (
    <Drawer
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={fm(m.progressTitle, { action: job.action_label })}
      description={fm(m.progressStarted, { name: job.created_by.name })}
      closeLabel={fm(m.close)}
      size="lg"
    >
      <div className="flex flex-col gap-4" data-bulk-progress={job.status}>
        <p className="text-sm font-semibold" role="status">
          {fm(statusLabel[job.status] ?? m.statusRunning)}
        </p>
        <div
          role="progressbar"
          aria-label={fm(m.progressLabel, { done: job.done, total: job.total })}
          aria-valuemin={0}
          aria-valuemax={job.total}
          aria-valuenow={job.done}
          className="h-3 w-full overflow-hidden rounded-full bg-surface-muted"
        >
          <div className="h-full bg-surface-inverse" style={{ width: `${job.percent}%` }} />
        </div>
        <p className="text-xs text-fg-muted">
          {fm(m.progressLabel, { done: job.done, total: job.total })}
        </p>
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {counters.map(([key, label, value]) => (
            <div key={key} className="rounded-md border border-border p-2" data-counter={key}>
              <dt className="text-xs text-fg-muted">{fm(label)}</dt>
              <dd className="text-xl font-bold tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
        {!finished ? (
          job.cancel_requested ? (
            <p className="text-sm text-fg-muted">{fm(m.cancelling)}</p>
          ) : (
            <Button
              variant="danger"
              onClick={() =>
                void bulkApi.cancel(job.id).then((r) => r.status === 200 && setJob(r.body))
              }
            >
              {fm(m.cancelRest)}
            </Button>
          )
        ) : (
          <section className="flex flex-col gap-2" aria-labelledby="bulk-results-heading">
            <h3 id="bulk-results-heading" className="text-sm font-semibold">
              {fm(m.results)}
            </h3>
            <div role="group" aria-label={fm(m.filterOutcome)} className="flex flex-wrap gap-1">
              {FILTERS.map((value) => (
                <Button
                  key={value || "all"}
                  size="sm"
                  variant={outcome === value ? "primary" : "secondary"}
                  aria-pressed={outcome === value}
                  onClick={() => setOutcome(value)}
                >
                  {fm(value ? outcomeLabel[value] : m.all)}
                </Button>
              ))}
            </div>
            {rows && rows.results.length ? (
              <table className="w-full text-sm" data-bulk-results="">
                <thead>
                  <tr className="border-b border-border text-xs text-fg-muted">
                    <th className="py-1 text-start">{fm(m.colOrganisation)}</th>
                    <th className="py-1 text-start">{fm(m.colOutcome)}</th>
                    <th className="py-1 text-start">{fm(m.colWhy)}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.results.map((row) => (
                    <tr
                      key={row.organisation.id}
                      className="border-b border-border"
                      data-outcome={row.outcome}
                    >
                      <td className="py-1">{row.organisation.name}</td>
                      <td className="py-1">{fm(outcomeLabel[row.outcome])}</td>
                      <td className="py-1 text-fg-muted">{row.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : rows ? (
              <p className="text-sm text-fg-muted">{fm(m.noResults)}</p>
            ) : null}
            <div className="flex flex-wrap gap-3">
              <a href={resultsCsvUrl(job.id)} className="text-sm font-semibold underline" download>
                {fm(m.downloadCsv)}
              </a>
              {job.export_ready ? (
                <a href={exportUrl(job.id)} className="text-sm font-semibold underline" download>
                  {fm(m.downloadExport)}
                </a>
              ) : null}
            </div>
          </section>
        )}
      </div>
    </Drawer>
  );
}
