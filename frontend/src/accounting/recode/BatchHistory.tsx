"use client";

/**
 * Find & recode — the history (C-07-T13): every recode, newest first, with who ran it and when,
 * its lines and status, the audit report (CSV, Excel, PDF) and **Undo** — available while every
 * period it touched is open; otherwise the button is disabled and the reason is shown beside it
 * (the entries in locked, closed or filed periods, or a later recode to undo first).
 */
import { Badge, Button, Dialog, formatDateTime, INPUT_BASE, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { recodeApi, type Batch, type BatchStatus, type ReportFormat } from "./api";
import { rm } from "./messages";

const TONES: Record<BatchStatus, "success" | "warning" | "neutral" | "danger" | "info"> = {
  draft: "neutral",
  running: "info",
  completed: "success",
  failed: "danger",
  undone: "warning",
};
const UNDOABLE: BatchStatus[] = ["completed", "failed"];
const FORMATS: ReportFormat[] = ["csv", "xlsx", "pdf"];

export function BatchHistory({ org, refresh = 0 }: { org: string; refresh?: number }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [batches, setBatches] = useState<Batch[] | null>(null);
  const [target, setTarget] = useState<Batch | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    const answer = await recodeApi.batches(org).catch(() => null);
    if (answer?.status !== 200) {
      setBatches([]);
      return;
    }
    const detailed = await Promise.all(
      answer.body.batches.map(async (batch) => {
        if (!UNDOABLE.includes(batch.status)) return batch;
        const one = await recodeApi.batch(org, batch.id).catch(() => null);
        return one?.status === 200 ? one.body : batch;
      }),
    );
    setBatches(detailed);
  }, [org]);

  useEffect(() => {
    void load();
  }, [load, refresh]);

  const undo = async () => {
    if (!target) return;
    setBusy(true);
    setError("");
    const answer = await recodeApi.undo(org, target.id, reason.trim()).catch(() => null);
    setBusy(false);
    if (answer?.status === 200) {
      setTarget(null);
      setReason("");
      setNotice(fm(rm.undone));
      await load();
      return;
    }
    setError(answer?.body?.detail || fm(rm.failed));
  };

  const why = (batch: Batch) => {
    if (!UNDOABLE.includes(batch.status))
      return batch.status === "running" ? fm(rm.undoNotYet) : "";
    const blocked = batch.undo?.blocked ?? [];
    if (batch.undo?.allowed || blocked.length === 0) return "";
    return fm(rm.undoBlocked, {
      reasons: blocked.map((b) => (b.number ? `${b.number} — ${b.message}` : b.message)).join("; "),
    });
  };

  return (
    <section className="flex flex-col gap-3" data-recode-history="">
      <h2 className="text-base font-semibold text-fg">{fm(rm.history)}</h2>
      <p role="status" className="text-sm text-fg-success">
        {notice}
      </p>
      {batches === null ? (
        <p className="text-sm text-fg-muted">{fm(rm.loading)}</p>
      ) : batches.length === 0 ? (
        <p className="text-sm text-fg-muted">{fm(rm.noHistory)}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-fg-muted">
                <th scope="col" className="p-1">
                  {fm(rm.colBatch)}
                </th>
                <th scope="col" className="p-1">
                  {fm(rm.colRun)}
                </th>
                <th scope="col" className="p-1 text-end">
                  {fm(rm.colLines)}
                </th>
                <th scope="col" className="p-1">
                  {fm(rm.colStatus)}
                </th>
                <th scope="col" className="p-1">
                  <span className="sr-only">{fm(rm.colActions)}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {batches.map((batch) => {
                const blockedText = why(batch);
                const canUndo = UNDOABLE.includes(batch.status) && Boolean(batch.undo?.allowed);
                const hintId = `${ids}-${batch.id}-why`;
                return (
                  <tr
                    key={batch.id}
                    className="border-t border-border align-top"
                    data-batch={batch.id}
                  >
                    <td className="p-1 font-medium">{batch.label}</td>
                    <td className="p-1">
                      {batch.executed_by && batch.executed_at
                        ? fm(rm.runBy, {
                            name: batch.executed_by.name,
                            when: formatDateTime(batch.executed_at, { locale }),
                          })
                        : ""}
                    </td>
                    <td className="p-1 text-end tabular-nums">{batch.line_count}</td>
                    <td className="p-1">
                      <Badge tone={TONES[batch.status]}>
                        {fm(rm.status, { status: batch.status })}
                      </Badge>
                    </td>
                    <td className="p-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {batch.status === "running" || batch.status === "draft"
                          ? null
                          : FORMATS.map((format) => (
                              <a
                                key={format}
                                className="text-fg-accent underline"
                                href={recodeApi.reportUrl(org, batch.id, format)}
                                download
                              >
                                {fm(rm.report, { format: format.toUpperCase() })}
                              </a>
                            ))}
                        {batch.status === "undone" ? null : (
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={!canUndo}
                            aria-describedby={blockedText ? hintId : undefined}
                            onClick={() => setTarget(batch)}
                          >
                            {fm(rm.undo)}
                          </Button>
                        )}
                      </div>
                      {blockedText ? (
                        <p id={hintId} className="mt-1 text-xs text-fg-warning" data-undo-why="">
                          {blockedText}
                        </p>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <Dialog
        open={target !== null}
        onOpenChange={(open) => {
          if (!open) {
            setTarget(null);
            setError("");
          }
        }}
        title={fm(rm.undoTitle, { name: target?.label ?? "" })}
        closeLabel={fm(rm.close)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setTarget(null)}>
              {fm(rm.cancel)}
            </Button>
            <Button variant="primary" disabled={busy} onClick={() => void undo()}>
              {fm(rm.undo)}
            </Button>
          </>
        }
      >
        <p className="text-sm text-fg">{fm(rm.undoBody)}</p>
        <label className="mt-3 flex flex-col gap-1 text-sm text-fg">
          {fm(rm.undoReason)}
          <input
            className={`${INPUT_BASE} border-border`}
            value={reason}
            maxLength={2000}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
        {error ? (
          <p role="alert" className="mt-2 text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
      </Dialog>
    </section>
  );
}
