"use client";

/**
 * Contact → Supplier statements (B-02-T12, gap-23): their statement and our bills in two columns,
 * matched pairs (by number, by amount and date, by hand), the unmatched on each side with a
 * difference summary at the top; match a line by hand and write a note on it.
 */
import { Button, formatDate, formatMoney, Input, Select, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { activityApi, type OurItem, type Reconciliation, type TheirLine } from "./activityApi";
import { tm } from "./tabMessages";

function TheirRow({
  line,
  ours,
  onMatch,
  onNote,
}: {
  line: TheirLine;
  ours: OurItem[];
  onMatch: (ref: string) => void;
  onNote: (note: string) => void;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [note, setNote] = useState(line.note);
  const label = fm(tm.lineText, {
    date: formatDate(line.date, { locale }),
    document: line.invoice_number || line.reference || "—",
    amount: formatMoney(line.amount, { locale }),
  });
  return (
    <li className="flex flex-col gap-2 p-3 text-sm" data-their-line={line.id}>
      <span className="font-semibold">{label}</span>
      {ours.length > 0 ? (
        <Select
          aria-label={fm(tm.matchTo, { line: label })}
          value={line.manual_ref || "none"}
          onValueChange={(value) => onMatch(value === "none" ? "" : value)}
          options={[
            { value: "none", label: fm(tm.choose) },
            ...ours.map((item) => ({
              value: item.ref,
              label: fm(tm.lineText, {
                date: formatDate(item.date, { locale }),
                document: item.document,
                amount: formatMoney(item.amount, { locale }),
              }),
            })),
          ]}
        />
      ) : null}
      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          onNote(note);
        }}
      >
        <Input
          aria-label={fm(tm.note, { line: label })}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <Button type="submit" size="sm">
          {fm(tm.saveNote)}
        </Button>
      </form>
    </li>
  );
}

export function ReconciliationTab({ org, id }: { org: string; id: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [statements, setStatements] = useState<{ id: string; statement_date: string }[]>([]);
  const [current, setCurrent] = useState("");
  const [report, setReport] = useState<Reconciliation | null>(null);

  useEffect(() => {
    void activityApi.supplierStatements(org, id).then((result) => {
      if (result.status !== 200) return;
      setStatements(result.body.results);
      setCurrent((value) => value || result.body.results[0]?.id || "");
    });
  }, [org, id]);

  const load = useCallback(async () => {
    if (!current) return;
    const result = await activityApi.reconciliation(org, id, current);
    if (result.status === 200) setReport(result.body);
  }, [org, id, current]);

  useEffect(() => {
    void load();
  }, [load]);

  if (statements.length === 0)
    return <p className="text-sm text-fg-muted">{fm(tm.noStatements)}</p>;
  const money = (amount: string) => formatMoney(amount, { locale });
  const update = (line: string, change: { manual_ref?: string; note?: string }) =>
    void activityApi.updateLine(org, id, current, line, change).then(() => load());

  return (
    <div className="flex flex-col gap-4" data-reconciliation-tab="">
      <Select
        aria-label={fm(tm.statementChoice)}
        value={current}
        onValueChange={setCurrent}
        options={statements.map((s) => ({
          value: s.id,
          label: formatDate(s.statement_date, { locale }),
        }))}
      />
      {report ? (
        <>
          <p role="status" className="text-base font-semibold" data-recon-totals="">
            {fm(tm.totals, {
              theirs: money(report.their_total),
              ours: money(report.our_total),
              difference: money(report.difference),
            })}
          </p>
          <section className="flex flex-col gap-2">
            <h3 className="text-sm font-semibold">{fm(tm.matched)}</h3>
            <ul className="flex flex-col gap-1 text-sm">
              {report.pairs.map((pair) => (
                <li key={pair.theirs.id}>
                  {fm(tm.pairLine, {
                    theirs: pair.theirs.invoice_number || pair.theirs.reference || pair.theirs.date,
                    ours: pair.ours.document,
                    how: fm(tm.how, { how: pair.how }),
                    difference: Number(pair.difference) === 0 ? "none" : money(pair.difference),
                  })}
                </li>
              ))}
            </ul>
          </section>
          <div className="grid gap-4 md:grid-cols-2">
            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold">{fm(tm.column, { side: fm(tm.theirs) })}</h3>
              <ul className="flex flex-col divide-y divide-border rounded-md border border-border">
                {report.unmatched_theirs.map((line) => (
                  <TheirRow
                    key={line.id}
                    line={line}
                    ours={report.unmatched_ours}
                    onMatch={(ref) => update(line.id, { manual_ref: ref })}
                    onNote={(note) => update(line.id, { note })}
                  />
                ))}
              </ul>
            </section>
            <section className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold">{fm(tm.column, { side: fm(tm.ours) })}</h3>
              <ul className="flex flex-col divide-y divide-border rounded-md border border-border text-sm">
                {report.unmatched_ours.map((item) => (
                  <li key={item.ref} className="p-3" data-our-item={item.document}>
                    {fm(tm.lineText, {
                      date: formatDate(item.date, { locale }),
                      document: item.document,
                      amount: money(item.amount),
                    })}
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}
