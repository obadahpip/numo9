"use client";

/**
 * Period close (C-06-T08, T09), `/o/:org/accounting/period-close`: a module × month timeline of
 * the fiscal year with a status pill per month — closed, locked (a lock date without a close),
 * open — navigable with the arrow keys; selecting a month shows its checklist (drafts, approvals,
 * unfiled tax periods, exceptions) with a link to the list that fixes each, and Close / Reopen
 * with their consequences in a dialog. Reopen is offered to advisers only (the server refuses
 * anyone else). "Close the fiscal year" runs the year-end roll.
 */
import { Badge, Button, Dialog, formatDate, type AppLocale } from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import { useFormatMessage } from "@/i18n";

import {
  periodCloseApi,
  type ChecklistItem,
  type MonthStatus,
  type Timeline,
  type TimelineMonth,
} from "./api";
import { pm } from "./messages";

const TONES: Record<MonthStatus, "success" | "warning" | "neutral"> = {
  closed: "success",
  locked: "warning",
  open: "neutral",
};

type Dialogs = "close" | "reopen" | "year" | null;

export function PeriodCloseScreen({ org }: { org: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [year, setYear] = useState<number | undefined>(undefined);
  const [data, setData] = useState<Timeline | null>(null);
  const [failed, setFailed] = useState(false);
  const [focus, setFocus] = useState<[number, number]>([0, 0]);
  const [selected, setSelected] = useState<[number, number] | null>(null);
  const [items, setItems] = useState<ChecklistItem[] | null>(null);
  const [dialog, setDialog] = useState<Dialogs>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const cells = useRef(new Map<string, HTMLButtonElement>());

  const load = useCallback(async () => {
    const answer = await periodCloseApi.timeline(org, year).catch(() => null);
    if (answer?.status === 200) {
      setData(answer.body);
      setFailed(false);
    } else setFailed(true);
  }, [org, year]);

  useEffect(() => {
    void load();
  }, [load]);

  const monthName = (iso: string, style: "long" | "short") =>
    new Intl.DateTimeFormat(locale, {
      month: style,
      ...(style === "long" ? { year: "numeric" as const } : {}),
      timeZone: "UTC",
    }).format(new Date(`${iso}T00:00:00Z`));
  const month = (m: TimelineMonth) => monthName(m.start, "long");
  const day = (value: string) => formatDate(value, { locale });

  const choose = async (row: number, col: number) => {
    setSelected([row, col]);
    setItems(null);
    const m = data?.modules[row]?.months[col];
    if (!m) return;
    const answer = await periodCloseApi.checklist(org, m.end).catch(() => null);
    if (answer?.status === 200) setItems(answer.body.items);
  };

  const onKey = (event: KeyboardEvent<HTMLButtonElement>, row: number, col: number) => {
    if (!data) return;
    const moves: Record<string, [number, number]> = {
      ArrowRight: [row, Math.min(11, col + 1)],
      ArrowLeft: [row, Math.max(0, col - 1)],
      ArrowDown: [Math.min(data.modules.length - 1, row + 1), col],
      ArrowUp: [Math.max(0, row - 1), col],
      Home: [row, 0],
      End: [row, 11],
    };
    const next = moves[event.key];
    if (!next) return;
    event.preventDefault();
    setFocus(next);
    cells.current.get(`${next[0]}-${next[1]}`)?.focus();
  };

  const act = async (run: () => Promise<{ status: number; body: { detail?: string } }>) => {
    setBusy(true);
    setError("");
    const answer = await run().catch(() => null);
    setBusy(false);
    if (answer && (answer.status === 200 || answer.status === 201)) {
      setDialog(null);
      setReason("");
      setNotice(fm(pm.saved));
      await load();
      if (selected) void choose(selected[0], selected[1]);
      return;
    }
    setError(answer?.body?.detail || fm(pm.failed));
  };

  if (failed) {
    return (
      <p role="alert" className="text-sm text-fg-danger">
        {fm(pm.failed)}
      </p>
    );
  }
  if (!data) return <p className="text-sm text-fg-muted">{fm(pm.loading)}</p>;

  const fiscalYear = Number(data.fiscal_year.end.slice(0, 4));
  const row = selected ? data.modules[selected[0]] : undefined;
  const cell = selected && row ? row.months[selected[1]] : undefined;
  const closeRecord = cell?.close ? data.closes.find((c) => c.id === cell.close) : undefined;
  const reopenTarget =
    closeRecord ?? (cell?.close === null ? undefined : (data.year_end ?? undefined));

  return (
    <div className="flex flex-col gap-4" data-period-close="">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-fg">{fm(pm.title)}</h1>
          <p className="max-w-3xl text-sm text-fg-muted">{fm(pm.intro)}</p>
          <p className="mt-1 text-sm font-medium text-fg">
            {fm(pm.year, { start: day(data.fiscal_year.start), end: day(data.fiscal_year.end) })}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setYear(fiscalYear - 1)}>
            {fm(pm.previousYear)}
          </Button>
          <Button variant="secondary" onClick={() => setYear(fiscalYear + 1)}>
            {fm(pm.nextYear)}
          </Button>
          {data.year_end ? null : (
            <Button variant="primary" onClick={() => setDialog("year")}>
              {fm(pm.yearEnd)}
            </Button>
          )}
        </div>
      </header>
      {data.year_end ? (
        <p className="text-sm text-fg" data-year-closed="">
          {fm(pm.yearClosed, {
            numbers: data.year_end.entries.map((e) => String(e.number ?? "")).join(", "),
          })}
        </p>
      ) : null}
      <p role="status" className="text-sm text-fg-success">
        {notice}
      </p>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <div className="flex flex-col gap-4 xl:flex-row">
        <div className="overflow-x-auto">
          <table aria-label={fm(pm.grid)} className="text-xs" data-close-grid="">
            <thead>
              <tr>
                <th scope="col" className="p-1 text-left text-fg-muted">
                  {fm(pm.module)}
                </th>
                {data.modules[0]?.months.map((m) => (
                  <th key={m.start} scope="col" className="p-1 text-fg-muted">
                    {monthName(m.start, "short")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.modules.map((mod, r) => (
                <tr key={mod.module} data-module={mod.module}>
                  <th scope="row" className="p-1 text-left font-medium text-fg">
                    {mod.label}
                  </th>
                  {mod.months.map((m, c) => (
                    <td key={m.start} className="p-0.5">
                      <button
                        type="button"
                        ref={(node) => {
                          if (node) cells.current.set(`${r}-${c}`, node);
                        }}
                        tabIndex={focus[0] === r && focus[1] === c ? 0 : -1}
                        aria-label={fm(pm.cell, {
                          module: mod.label,
                          month: month(m),
                          status: fm(pm.status, { status: m.status }),
                        })}
                        aria-pressed={selected?.[0] === r && selected?.[1] === c}
                        data-month={m.end}
                        data-status={m.status}
                        onKeyDown={(e) => onKey(e, r, c)}
                        onFocus={() => setFocus([r, c])}
                        onClick={() => void choose(r, c)}
                        className="rounded-sm focus-visible:outline-2 focus-visible:outline-border-focus"
                      >
                        <Badge tone={TONES[m.status]}>{fm(pm.status, { status: m.status })}</Badge>
                      </button>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {row && cell ? (
          <section
            aria-labelledby={`${ids}-checklist`}
            className="flex min-w-72 flex-col gap-2 rounded-md border border-border p-3 text-sm"
            data-checklist=""
          >
            <h2 id={`${ids}-checklist`} className="font-semibold text-fg">
              {fm(pm.checklistTitle, { module: row.label, month: month(cell) })}
            </h2>
            <p className="text-fg-muted">{fm(pm.checklistIntro)}</p>
            <ul className="flex flex-col gap-1">
              {(items ?? []).map((item) => (
                <li
                  key={item.key}
                  className="flex items-center justify-between gap-2"
                  data-item={item.key}
                >
                  <span>{fm(pm.itemCount, { label: item.label, count: item.count })}</span>
                  {item.count ? (
                    <Link href={item.link} className="text-fg-link underline">
                      {fm(pm.review)}
                    </Link>
                  ) : null}
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-2">
              {cell.status !== "closed" ? (
                <Button variant="primary" onClick={() => setDialog("close")}>
                  {fm(pm.close, { month: month(cell) })}
                </Button>
              ) : data.is_adviser ? (
                <Button variant="secondary" onClick={() => setDialog("reopen")}>
                  {fm(pm.reopen)}
                </Button>
              ) : (
                <p className="text-fg-muted">{fm(pm.adviserOnly)}</p>
              )}
            </div>
          </section>
        ) : null}
      </div>
      <Dialog
        open={dialog === "close" && Boolean(cell)}
        onOpenChange={(open) => setDialog(open ? "close" : null)}
        title={row && cell ? fm(pm.closeTitle, { module: row.label, date: day(cell.end) }) : ""}
        closeLabel={fm(pm.closeDialog)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDialog(null)}>
              {fm(pm.cancel)}
            </Button>
            <Button
              variant="primary"
              disabled={busy}
              onClick={() =>
                row && cell && void act(() => periodCloseApi.close(org, row.module, cell.end))
              }
            >
              {fm(pm.confirmClose)}
            </Button>
          </>
        }
      >
        <p className="text-sm text-fg">
          {row && cell ? fm(pm.closeBody, { module: row.label, date: day(cell.end) }) : null}
        </p>
      </Dialog>
      <Dialog
        open={dialog === "reopen" && Boolean(reopenTarget)}
        onOpenChange={(open) => setDialog(open ? "reopen" : null)}
        title={
          row && reopenTarget
            ? fm(pm.reopenTitle, { module: row.label, date: day(reopenTarget.period_end) })
            : ""
        }
        closeLabel={fm(pm.closeDialog)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDialog(null)}>
              {fm(pm.cancel)}
            </Button>
            <Button
              variant="danger"
              disabled={busy || !reason.trim()}
              onClick={() =>
                reopenTarget &&
                void act(() => periodCloseApi.reopen(org, reopenTarget.id, reason.trim()))
              }
            >
              {fm(pm.confirmReopen)}
            </Button>
          </>
        }
      >
        <p className="text-sm text-fg">{fm(pm.reopenBody)}</p>
        {reopenTarget?.kind === "year_end" ? (
          <p className="mt-1 text-sm text-fg">{fm(pm.reopenYearBody)}</p>
        ) : null}
        <label htmlFor={`${ids}-reason`} className="mt-2 block text-sm font-medium text-fg">
          {fm(pm.reason)}
        </label>
        <textarea
          id={`${ids}-reason`}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md border border-border bg-surface p-2 text-sm text-fg"
        />
      </Dialog>
      <Dialog
        open={dialog === "year"}
        onOpenChange={(open) => setDialog(open ? "year" : null)}
        title={fm(pm.yearEndTitle, { date: day(data.fiscal_year.end) })}
        closeLabel={fm(pm.closeDialog)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDialog(null)}>
              {fm(pm.cancel)}
            </Button>
            <Button
              variant="primary"
              disabled={busy}
              onClick={() => void act(() => periodCloseApi.yearEnd(org, data.fiscal_year.end))}
            >
              {fm(pm.yearEnd)}
            </Button>
          </>
        }
      >
        <p className="text-sm text-fg">{fm(pm.yearEndBody, { date: day(data.fiscal_year.end) })}</p>
      </Dialog>
    </div>
  );
}
