"use client";

/**
 * Receive screen (E-01-T12): one row per PO line — ordered, received before, outstanding — and a
 * big numeric "Receiving now" input (barcode-ready: a scanner types the quantity and Enter).
 * **Enter moves to the next line**; on the last line it records the receipt. A line received
 * beyond what was ordered warns as it is typed; the server's tolerance (E-01-T04) decides: within
 * it, received; beyond it, "More than ordered" lists the lines and "Receive anyway" confirms
 * (blocked organisations get the refusal only).
 */
import { Button, ErrorState, Input, Skeleton } from "@numo9/ui";
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import { useFormatMessage } from "@/i18n";

import {
  purchaseOrdersApi,
  receiptsApi,
  type OverReceipt,
  type PurchaseOrder,
  type Refusal,
} from "./api";
import { orderUrl } from "./PurchaseOrderEditor";
import { receive as m, statusLabels } from "./messages";

const today = () => new Date().toISOString().slice(0, 10);
const qty = (value: string | number) => String(Number(value));
const RECEIVABLE = ["approved", "partially_received", "received"];

/** Quantity typed beyond what is left to receive on a line (0 when within). */
export function overBy(ordered: string, received: string, now: string): number {
  const extra = Number(received) + Number(now || "0") - Number(ordered);
  return extra > 0 ? Math.round(extra * 10000) / 10000 : 0;
}

export function ReceiveScreen({ org, id }: { org: string; id: string }) {
  const fm = useFormatMessage();
  const ids = useId();
  const [order, setOrder] = useState<PurchaseOrder | null>(null);
  const [failed, setFailed] = useState(false);
  const [now, setNow] = useState<Record<string, string>>({});
  const [date, setDate] = useState(today);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [over, setOver] = useState<OverReceipt[] | null>(null);
  const inputs = useRef<(HTMLInputElement | null)[]>([]);

  const load = useCallback(async () => {
    const result = await purchaseOrdersApi.get(org, id);
    if (result.status === 200 && result.body.id) {
      setOrder(result.body);
      setNow({});
    } else setFailed(true);
  }, [org, id]);

  useEffect(() => {
    void load();
  }, [load]);

  const record = async (confirmOver = false) => {
    if (!order || busy) return;
    const lines = order.lines
      .filter((line) => Number(now[line.id] || "0") > 0)
      .map((line) => ({ po_line: line.id, quantity: now[line.id] as string }));
    setRefusal(null);
    setStatus("");
    if (!lines.length) {
      setRefusal({ detail: fm(m.nothing) });
      return;
    }
    setBusy(true);
    const result = await receiptsApi.create(org, {
      purchase_order: order.id,
      date,
      notes,
      lines,
      confirm_over: confirmOver,
    });
    setBusy(false);
    if (result.status === 201) {
      setOver(null);
      setNotes("");
      const fresh = await purchaseOrdersApi.get(org, order.id);
      if (fresh.status === 200 && fresh.body.id) {
        setOrder(fresh.body);
        setNow({});
        const outstanding = fresh.body.lines.reduce((sum, l) => sum + Number(l.outstanding), 0);
        setStatus(fm(m.done, { outstanding }));
      }
      return;
    }
    const body = (result.body && typeof result.body === "object" ? result.body : {}) as Refusal & {
      over?: OverReceipt[];
    };
    if (body.code === "purchases.receipt.over_tolerance_confirm" && body.over) {
      setOver(body.over);
      return;
    }
    setOver(body.code === "purchases.receipt.over_tolerance" && body.over ? body.over : null);
    setRefusal(body);
  };

  const onKey = (index: number) => (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const next = inputs.current[index + 1];
    if (next) {
      next.focus();
      next.select();
    } else void record();
  };

  if (failed) {
    return (
      <ErrorState
        title={fm(m.title, { number: "" })}
        retryLabel={fm(m.back)}
        onRetry={() => window.location.reload()}
      />
    );
  }
  if (!order) return <Skeleton className="h-96" aria-busy="true" />;

  const receivable = RECEIVABLE.includes(order.status);
  const cell = "px-3 py-2 text-end tabular-nums";
  const head = "px-3 py-2 text-end text-xs font-semibold text-fg-muted";

  return (
    <section aria-labelledby={`${ids}-title`} className="flex flex-col gap-5" data-receive="">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 id={`${ids}-title`} className="text-2xl font-semibold text-fg">
            {fm(m.title, { number: order.number })}
          </h1>
          <p className="text-sm text-fg-muted">
            {fm(m.supplier, { supplier: order.supplier.name })}
          </p>
        </div>
        <a href={orderUrl(org, order.id)} className="text-sm text-fg underline">
          {fm(m.back)}
        </a>
      </div>
      {!receivable ? (
        <p className="rounded-md bg-surface-info-subtle p-3 text-sm text-fg" role="note">
          {fm(m.notReceivable, { status: fm(statusLabels[order.status]) })}
        </p>
      ) : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(m.date)}
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(m.notes)}
          <Input value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-fg-muted" id={`${ids}-hint`}>
          {fm(m.keyboardHint)}
        </p>
        <Button
          type="button"
          variant="secondary"
          disabled={!receivable}
          onClick={() =>
            setNow(
              Object.fromEntries(
                order.lines
                  .filter((line) => Number(line.outstanding) > 0)
                  .map((line) => [line.id, qty(line.outstanding)]),
              ),
            )
          }
        >
          {fm(m.fillAll)}
        </Button>
      </div>
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm" aria-label={fm(m.table)}>
          <thead className="bg-surface-muted">
            <tr>
              <th scope="col" className="px-3 py-2 text-start text-xs font-semibold text-fg-muted">
                {fm(m.line)}
              </th>
              <th scope="col" className={head}>
                {fm(m.ordered)}
              </th>
              <th scope="col" className={head}>
                {fm(m.received)}
              </th>
              <th scope="col" className={head}>
                {fm(m.outstanding)}
              </th>
              <th scope="col" className={head}>
                {fm(m.now)}
              </th>
            </tr>
          </thead>
          <tbody>
            {order.lines.map((line, index) => {
              const value = now[line.id] ?? "";
              const extra = overBy(line.quantity, line.quantity_received, value);
              const label = line.description || String(index + 1);
              return (
                <tr
                  key={line.id}
                  className="border-t border-border"
                  data-over={extra > 0 ? "" : undefined}
                >
                  <th scope="row" className="px-3 py-2 text-start font-normal">
                    {label}
                  </th>
                  <td className={cell}>{qty(line.quantity)}</td>
                  <td className={cell}>{qty(line.quantity_received)}</td>
                  <td className={cell}>{qty(line.outstanding)}</td>
                  <td className="px-3 py-2 text-end">
                    <Input
                      ref={(element) => {
                        inputs.current[index] = element;
                      }}
                      inputMode="decimal"
                      autoComplete="off"
                      aria-label={fm(m.nowFor, { line: label })}
                      aria-describedby={`${ids}-hint`}
                      numeric
                      disabled={!receivable}
                      value={value}
                      onChange={(e) =>
                        setNow((all) => ({ ...all, [line.id]: e.target.value.replace(",", ".") }))
                      }
                      onKeyDown={onKey(index)}
                      className="ms-auto h-14 w-32 text-end text-2xl tabular-nums"
                    />
                    {extra > 0 ? (
                      <span className="mt-1 block text-xs font-semibold text-fg-warning">
                        {fm(m.overLine, { quantity: qty(extra) })}
                      </span>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {over ? (
        <div
          role="alert"
          className="flex flex-col gap-2 rounded-md border border-border bg-surface-warning-subtle p-3 text-sm text-fg"
          data-over-receipt=""
        >
          <h2 className="font-semibold">{fm(m.overTitle)}</h2>
          <ul className="list-disc ps-5">
            {over.map((row) => (
              <li key={row.line}>
                {fm(m.overRow, {
                  line: row.line,
                  received: qty(row.received),
                  ordered: qty(row.ordered),
                  allowed: qty(row.allowed),
                })}
              </li>
            ))}
          </ul>
          {!refusal ? (
            <div>
              <Button type="button" variant="primary" onClick={() => void record(true)}>
                {fm(m.confirmOver)}
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
      {refusal ? (
        <p
          role="alert"
          className="rounded-md border border-border-danger p-3 text-sm font-semibold text-fg-danger"
          data-refusal={refusal.code ?? ""}
        >
          {refusal.detail}
        </p>
      ) : null}
      <p role="status" className="text-sm text-fg">
        {status}
      </p>
      <div>
        <Button
          type="button"
          variant="primary"
          disabled={busy || !receivable}
          onClick={() => void record()}
        >
          {busy ? fm(m.recording) : fm(m.record)}
        </Button>
      </div>
    </section>
  );
}
