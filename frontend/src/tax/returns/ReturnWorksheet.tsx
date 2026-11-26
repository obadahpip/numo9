"use client";

/**
 * The GST/HST return worksheet (G-03-T11), `/o/:org/tax/returns/:id`: the GST34 lines in the
 * CRA's layout, each line that comes from the books opening the documents behind it in a drawer;
 * the typed lines (104, 107, 110, 111, 113B) as fields on a draft; the status stepper (prepare →
 * review → file); and, on a draft, the "books changed since" banner with Recalculate. Review and
 * send back here; mark as filed and amend in `ReturnActions` (G-03-T12).
 */
import {
  Button,
  ErrorState,
  INPUT_BASE,
  SkeletonText,
  formatDate,
  formatMoney,
  type AppLocale,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { returnUrl, returnsApi, type ReturnLine, type TaxReturn } from "./api";
import { LineDrillDrawer } from "./LineDrillDrawer";
import { retm } from "./messages";
import { ReturnActions } from "./ReturnActions";
import { ReturnStepper } from "./ReturnStepper";

/** Lines shown as totals (bold, ruled above). */
const TOTALS = new Set(["105", "108", "109", "112", "113A", "113C"]);

export interface ReturnWorksheetProps {
  org: string;
  id: string;
}

export function ReturnWorksheet({ org, id }: ReturnWorksheetProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [data, setData] = useState<TaxReturn | null>(null);
  const [failed, setFailed] = useState(false);
  const [entries, setEntries] = useState<Record<string, string>>({});
  const [drill, setDrill] = useState<ReturnLine | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [reason, setReason] = useState("");
  const [sendingBack, setSendingBack] = useState(false);

  const show = useCallback((answer: TaxReturn) => {
    setData(answer);
    const values: Record<string, string> = {};
    for (const line of answer.lines) if (line.entry) values[line.line] = line.amount;
    setEntries(values);
  }, []);

  const load = useCallback(async () => {
    setFailed(false);
    const answer = await returnsApi.get(org, id);
    if (answer.status === 200) show(answer.body);
    else setFailed(true);
  }, [org, id, show]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(run: () => ReturnType<typeof returnsApi.get>, done: string) {
    setBusy(true);
    setError("");
    setNotice("");
    const answer = await run();
    setBusy(false);
    if (answer.status === 200 || answer.status === 201) {
      show(answer.body);
      setNotice(done);
      return true;
    }
    setError(answer.body?.detail ?? fm(retm.loadFailed));
    return false;
  }

  if (failed) {
    return (
      <ErrorState
        title={fm(retm.loadFailed)}
        retryLabel={fm(retm.retry)}
        onRetry={() => void load()}
      />
    );
  }
  if (!data) return <SkeletonText lines={8} />;

  const draft = data.status === "draft" && data.is_current;
  const money = (value: string) => formatMoney(value, { locale, accounting: true });
  const period = fm(retm.range, {
    start: formatDate(data.period.start, { locale }),
    end: formatDate(data.period.end, { locale }),
  });
  const changed = data.changed ?? [];

  return (
    <div className="flex flex-col gap-4" data-testid="return-worksheet">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href={`/o/${encodeURIComponent(org)}/tax/returns`} className="text-sm">
            {fm(retm.backToList)}
          </Link>
          <h1 className="text-xl font-semibold">{fm(retm.worksheetTitle, { period })}</h1>
          <p className="text-sm text-fg-muted">
            {fm(retm.meta, { version: data.version, method: data.method, status: data.status })}
          </p>
          {data.prepared_by ? (
            <p className="text-sm text-fg-muted">
              {data.reviewed_by
                ? fm(retm.people, {
                    prepared: data.prepared_by.name,
                    reviewed: data.reviewed_by.name,
                  })
                : fm(retm.preparedBy, { name: data.prepared_by.name })}
            </p>
          ) : null}
        </div>
        <div className="flex gap-2">
          <a className="text-sm" href={returnsApi.pdfUrl(org, id)} download>
            {fm(retm.exportPdf)}
          </a>
          <a className="text-sm" href={returnsApi.csvUrl(org, id)} download>
            {fm(retm.exportCsv)}
          </a>
        </div>
      </div>

      <ReturnStepper status={data.status} />

      {!data.is_current && data.versions?.[0] ? (
        <div role="status" className="rounded border border-border bg-surface-subtle p-3 text-sm">
          <span className="me-1">{fm(retm.notCurrent)}</span>
          <Link href={returnUrl(org, data.versions[0].id)}>{fm(retm.openCurrent)}</Link>
        </div>
      ) : null}

      {draft && changed.length > 0 ? (
        <section
          aria-labelledby="return-changed"
          className="rounded border border-fg-warning bg-surface-warning p-3"
          data-testid="return-changed"
        >
          <h2 id="return-changed" className="font-semibold">
            {fm(retm.changedTitle)}
          </h2>
          <ul className="my-2 text-sm">
            {changed.map((c) => (
              <li key={c.line}>
                {fm(retm.changedLine, { line: c.line, was: money(c.was), now: money(c.now) })}
              </li>
            ))}
          </ul>
          <Button
            size="sm"
            variant="primary"
            disabled={busy}
            onClick={() => void act(() => returnsApi.recalculate(org, id), fm(retm.recalculated))}
          >
            {fm(retm.recalculate)}
          </Button>
        </section>
      ) : null}

      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="text-sm text-fg-success">
          {notice}
        </p>
      ) : null}

      <table className="w-full max-w-3xl text-sm" data-testid="return-lines">
        <thead>
          <tr className="text-fg-muted">
            <th className="w-16 py-1 text-start font-medium">{fm(retm.line)}</th>
            <th className="py-1 text-start font-medium">{fm(retm.description)}</th>
            <th className="w-44 py-1 text-end font-medium">{fm(retm.amount)}</th>
          </tr>
        </thead>
        <tbody>
          {data.lines.map((line) => (
            <tr
              key={line.line}
              data-line={line.line}
              className={TOTALS.has(line.line) ? "border-t border-border font-semibold" : ""}
            >
              <td className="py-1 tabular-nums">{line.line}</td>
              <td className="py-1">{line.label}</td>
              <td className="py-1 text-end tabular-nums">
                {draft && line.entry ? (
                  <input
                    className={`${INPUT_BASE} w-36 text-end`}
                    inputMode="decimal"
                    aria-label={fm(retm.entryLabel, { line: line.line })}
                    value={entries[line.line] ?? ""}
                    onChange={(e) => setEntries({ ...entries, [line.line]: e.target.value })}
                  />
                ) : line.drill ? (
                  <button
                    type="button"
                    className="tabular-nums text-fg-link underline"
                    aria-label={fm(retm.showDocuments, { line: line.line })}
                    onClick={() => setDrill(line)}
                  >
                    {money(line.amount)}
                  </button>
                ) : (
                  money(line.amount)
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="flex flex-wrap items-center gap-3">
        {draft ? (
          <>
            <Button
              disabled={busy}
              onClick={() =>
                void act(() => returnsApi.recalculate(org, id, entries), fm(retm.recalculated))
              }
            >
              {fm(retm.saveEntries)}
            </Button>
            <Button
              variant="primary"
              disabled={busy}
              onClick={() => void act(() => returnsApi.review(org, id), fm(retm.reviewed))}
            >
              {fm(retm.review)}
            </Button>
            <span className="text-sm text-fg-muted">{fm(retm.reviewHint)}</span>
          </>
        ) : null}
        {data.status === "reviewed" ? (
          sendingBack ? (
            <form
              className="flex flex-wrap items-end gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                void act(() => returnsApi.sendBack(org, id, reason), fm(retm.sentBack)).then(
                  (ok) => {
                    if (ok) {
                      setSendingBack(false);
                      setReason("");
                    }
                  },
                );
              }}
            >
              <label className="flex flex-col text-sm">
                {fm(retm.sendBackReason)}
                <input
                  className={INPUT_BASE}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
              <Button type="submit" disabled={busy}>
                {fm(retm.sendBack)}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setSendingBack(false)}>
                {fm(retm.cancel)}
              </Button>
            </form>
          ) : (
            <Button onClick={() => setSendingBack(true)}>{fm(retm.sendBack)}</Button>
          )
        ) : null}
        <ReturnActions org={org} data={data} onChange={show} />
      </div>

      {data.versions && data.versions.length > 1 ? (
        <section aria-labelledby="return-versions" className="text-sm">
          <h2 id="return-versions" className="font-semibold">
            {fm(retm.versions)}
          </h2>
          <ul data-testid="return-versions">
            {data.versions.map((v) => (
              <li key={v.id}>
                {v.id === data.id ? (
                  fm(retm.statusVersion, { status: v.status, version: v.version })
                ) : (
                  <Link href={returnUrl(org, v.id)}>
                    {fm(retm.statusVersion, { status: v.status, version: v.version })}
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <LineDrillDrawer org={org} returnId={id} line={drill} onClose={() => setDrill(null)} />
    </div>
  );
}
