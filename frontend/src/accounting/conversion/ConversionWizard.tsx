"use client";

/**
 * Conversion balances wizard (C-05-T10), `/o/:org/accounting/conversion`: a stepper — Conversion
 * date → Bank and cash → Open invoices → Open bills → Other balances → Review — whose progress is
 * **saved on the server** (`step`, `completed_steps`): "Save and continue" saves the step's data,
 * marks it done and moves on; leaving the page and coming back resumes at the saved step. Every
 * step can be revisited from the stepper. A finalised conversion opens on Review, read-only.
 */
import { Button, Checkbox, formatDate, Input, type AppLocale, type PickerAccount } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useState } from "react";

import { accountsApi } from "@/accounts/api";
import { pickerAccount } from "@/accounts/picker";
import { useFormatMessage } from "@/i18n";

import {
  conversionApi,
  STEPS,
  type Line,
  type OpeningDocument,
  type Overview,
  type StepKey,
} from "./api";
import { BalancesGrid, newBalanceRow, type BalanceRow } from "./BalancesGrid";
import { cm } from "./messages";

const STEP_MESSAGES = {
  date: cm.stepDate,
  bank: cm.stepBank,
  invoices: cm.stepInvoices,
  bills: cm.stepBills,
  other: cm.stepOther,
  review: cm.stepReview,
} as const;

type Group = "bank" | "other";

function rowsOf(lines: Line[], group: Group): BalanceRow[] {
  return lines
    .filter((line) => (group === "bank") === line.account.is_bank)
    .map((line) => ({
      ...newBalanceRow(line.account.id),
      debit: Number(line.debit) ? line.debit : "",
      credit: Number(line.credit) ? line.credit : "",
      description: line.description,
    }));
}

export interface ConversionWizardProps {
  org: string;
  /** The difference meter and Finalise (C-05-T11), rendered under the steps. */
  renderMeter?: (props: MeterSlot) => React.ReactNode;
  /** The open invoices / bills grid (C-05-T12). */
  renderDocuments?: (props: DocumentsSlot) => React.ReactNode;
}

export interface MeterSlot {
  overview: Overview;
  rows: BalanceRow[];
  readOnly: boolean;
  lockBalances: boolean;
  onFinalised: (overview: Overview) => void;
}

export interface DocumentsSlot {
  kind: "invoice" | "bill";
  documents: OpeningDocument[];
  readOnly: boolean;
  onChanged: () => void;
}

export function ConversionWizard({ org, renderMeter, renderDocuments }: ConversionWizardProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [failed, setFailed] = useState(false);
  const [accounts, setAccounts] = useState<PickerAccount[]>([]);
  const [rows, setRows] = useState<Record<Group, BalanceRow[]>>({ bank: [], other: [] });
  const [saved, setSaved] = useState<Record<Group, string[]>>({ bank: [], other: [] });
  const [documents, setDocuments] = useState<Record<"invoice" | "bill", OpeningDocument[]>>({
    invoice: [],
    bill: [],
  });
  const [problems, setProblems] = useState<Record<number, string>>({});
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadLines = useCallback(async () => {
    const answer = await conversionApi.lines(org).catch(() => null);
    if (answer?.status !== 200) return;
    const bank = rowsOf(answer.body.lines, "bank");
    const other = rowsOf(answer.body.lines, "other");
    setRows({ bank, other });
    setSaved({ bank: bank.map((r) => r.account), other: other.map((r) => r.account) });
  }, [org]);

  const loadDocuments = useCallback(async () => {
    const [invoices, bills] = await Promise.all([
      conversionApi.documents(org, "invoice").catch(() => null),
      conversionApi.documents(org, "bill").catch(() => null),
    ]);
    setDocuments({
      invoice: invoices?.status === 200 ? invoices.body.documents : [],
      bill: bills?.status === 200 ? bills.body.documents : [],
    });
  }, [org]);

  const load = useCallback(async () => {
    const answer = await conversionApi.overview(org).catch(() => null);
    if (answer?.status !== 200) {
      setFailed(true);
      return;
    }
    setOverview(answer.body);
    setFailed(false);
    if (answer.body.session) {
      setDate(answer.body.session.conversion_date);
      await Promise.all([loadLines(), loadDocuments()]);
    }
  }, [org, loadLines, loadDocuments]);

  useEffect(() => {
    void load();
    void accountsApi
      .list(org, "active")
      .then((answer) => {
        if (answer.status === 200) setAccounts(answer.body.results.map(pickerAccount));
      })
      .catch(() => undefined);
  }, [org, load]);

  const bankAccounts = useMemo(() => accounts.filter((a) => a.isBank), [accounts]);
  const otherAccounts = useMemo(() => accounts.filter((a) => !a.isBank), [accounts]);

  if (failed) {
    return (
      <p role="alert" className="text-sm text-fg-danger">
        {fm(cm.failed)}
      </p>
    );
  }
  if (!overview) return <p className="text-sm text-fg-muted">{fm(cm.loading)}</p>;

  const session = overview.session;
  const finalised = session?.status === "finalised";
  const current: StepKey = !session ? "date" : finalised ? "review" : session.step;
  const done = new Set(session?.completed_steps ?? []);
  const index = STEPS.indexOf(current);

  const run = async <T,>(
    action: () => Promise<{ status: number; body: T & { detail?: string } }>,
  ): Promise<(T & { detail?: string }) | null> => {
    setBusy(true);
    setError("");
    setNotice("");
    const answer = await action().catch(() => null);
    setBusy(false);
    if (answer && answer.status >= 200 && answer.status < 300) return answer.body;
    setError(answer?.body?.detail || fm(cm.failed));
    return null;
  };

  /** Save the step's own data (balances of the bank / other step). */
  const saveStep = async (step: StepKey): Promise<boolean> => {
    if (step !== "bank" && step !== "other") return true;
    const group: Group = step;
    const current = rows[group].filter((r) => r.account);
    const kept = new Set(current.map((r) => r.account));
    const removed = saved[group].filter((account) => !kept.has(account));
    const body = [
      ...current.map((r) => ({
        account: r.account,
        debit: r.debit,
        credit: r.credit,
        description: r.description,
      })),
      ...removed.map((account) => ({ account, debit: "", credit: "" })),
    ];
    setBusy(true);
    setError("");
    const answer = await conversionApi.setLines(org, body).catch(() => null);
    setBusy(false);
    if (answer?.status === 200) {
      setProblems({});
      await loadLines();
      return true;
    }
    const found: Record<number, string> = {};
    for (const problem of (answer?.body.rows ?? []) as { row: number; message: string }[]) {
      if (problem.row <= current.length) found[problem.row - 1] = problem.message;
    }
    setProblems(found);
    setError(answer?.body.detail || fm(cm.failed));
    return false;
  };

  const go = async (step: StepKey, complete?: StepKey) => {
    if (!session || finalised) return;
    const completed = complete ? [...done, complete] : [...done];
    const body = await run(() =>
      conversionApi.save(org, { step, completed_steps: completed as StepKey[] }),
    );
    if (body) {
      setOverview(body);
      setProblems({});
    }
  };

  const next = async () => {
    if (!(await saveStep(current))) return;
    const following: StepKey = STEPS[Math.min(index + 1, STEPS.length - 1)] ?? "review";
    await go(following, current);
    setNotice(fm(cm.saved));
  };

  const start = async () => {
    const body = await run(() => conversionApi.start(org, date));
    if (body) {
      const moved = await run(() =>
        conversionApi.save(org, { step: "bank", completed_steps: ["date"] }),
      );
      setOverview(moved ?? body);
    }
  };

  const saveDate = async () => {
    const body = await run(() => conversionApi.save(org, { conversion_date: date }));
    if (body) setOverview(body);
  };

  const day = (value: string) => formatDate(value, { locale });

  return (
    <div className="flex flex-col gap-4 pb-28" data-conversion="" data-step={current}>
      <header>
        <h1 className="text-xl font-semibold text-fg">{fm(cm.title)}</h1>
        <p className="max-w-3xl text-sm text-fg-muted">{fm(cm.intro)}</p>
      </header>

      <nav aria-label={fm(cm.steps)}>
        <ol className="flex flex-wrap gap-2">
          {STEPS.map((step, i) => {
            const isDone = done.has(step) || (finalised && step !== "review");
            return (
              <li key={step}>
                <button
                  type="button"
                  data-step-key={step}
                  data-done={isDone || undefined}
                  aria-current={step === current ? "step" : undefined}
                  disabled={!session || finalised || busy}
                  onClick={() => void go(step)}
                  className={
                    step === current
                      ? "rounded-full bg-surface-inverse px-3 py-1 text-sm font-medium text-fg-inverse"
                      : "rounded-full border border-border px-3 py-1 text-sm text-fg disabled:opacity-60"
                  }
                  aria-label={fm(cm.stepState, {
                    n: i + 1,
                    name: fm(STEP_MESSAGES[step]),
                    done: isDone ? "yes" : "no",
                  })}
                >
                  <span aria-hidden="true">
                    {fm(cm.stepState, {
                      n: i + 1,
                      name: fm(STEP_MESSAGES[step]),
                      done: isDone ? "yes" : "no",
                    })}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </nav>

      <section aria-labelledby={`${ids}-step`} className="flex flex-col gap-3">
        <h2 id={`${ids}-step`} className="text-lg font-semibold text-fg">
          {fm(STEP_MESSAGES[current])}
        </h2>

        {current === "date" ? (
          <div className="flex max-w-md flex-col gap-2">
            <label htmlFor={`${ids}-date`} className="text-sm font-medium text-fg">
              {fm(cm.dateLabel)}
            </label>
            <Input
              id={`${ids}-date`}
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              aria-describedby={`${ids}-date-help`}
            />
            <p id={`${ids}-date-help`} className="text-sm text-fg-muted">
              {fm(cm.dateHelp)}
            </p>
            <div className="flex gap-2">
              {session ? (
                <>
                  <Button variant="secondary" disabled={busy || !date} onClick={saveDate}>
                    {fm(cm.save)}
                  </Button>
                  <Button variant="primary" disabled={busy} onClick={next}>
                    {fm(cm.next)}
                  </Button>
                </>
              ) : (
                <Button variant="primary" disabled={busy || !date} onClick={start}>
                  {fm(cm.start)}
                </Button>
              )}
            </div>
          </div>
        ) : null}

        {current === "bank" || current === "other" ? (
          <>
            <p className="max-w-3xl text-sm text-fg-muted">
              {fm(current === "bank" ? cm.bankIntro : cm.otherIntro)}
            </p>
            <BalancesGrid
              name={current}
              rows={rows[current]}
              onChange={(next) => setRows((all) => ({ ...all, [current]: next }))}
              accounts={current === "bank" ? bankAccounts : otherAccounts}
              problems={problems}
            />
          </>
        ) : null}

        {current === "invoices" || current === "bills"
          ? renderDocuments?.({
              kind: current === "invoices" ? "invoice" : "bill",
              documents: documents[current === "invoices" ? "invoice" : "bill"],
              readOnly: finalised,
              onChanged: () => void loadDocuments().then(load),
            })
          : null}

        {current === "review" && session ? (
          <div className="flex flex-col gap-3" data-review="">
            {finalised ? (
              <p className="text-sm font-medium text-fg" data-finalised="">
                {fm(cm.finalised, {
                  date: day((session.finalised_at ?? "").slice(0, 10) || session.conversion_date),
                  number: session.opening_entry?.number ?? "",
                })}
                <span className="ms-1">
                  {fm(cm.corrections, { count: session.corrections.length })}
                </span>
              </p>
            ) : (
              <p className="max-w-3xl text-sm text-fg-muted">{fm(cm.reviewIntro)}</p>
            )}
            <ul className="flex flex-col gap-1 text-sm text-fg" data-controls="">
              {(overview.difference?.controls ?? []).map((check) => (
                <li
                  key={check.role}
                  data-control={check.role}
                  data-matches={check.matches || undefined}
                  className={check.matches ? "" : "text-fg-danger"}
                >
                  {fm(cm.control, {
                    label: check.label,
                    control: check.control,
                    documents: check.documents,
                    count: check.count,
                  })}
                </li>
              ))}
            </ul>
            {overview.difference?.opening_equity_missing ? (
              <p role="note" className="text-sm text-fg-warning" data-equity-missing="">
                {fm(cm.equityMissing)}
              </p>
            ) : null}
            {(overview.difference?.warnings ?? []).map((warning) => (
              <p key={warning.message} role="note" className="text-sm text-fg-warning">
                {warning.message}
              </p>
            ))}
            {finalised ? null : (
              <Checkbox
                label={fm(cm.lockBalances)}
                checked={session.lock_balances}
                onCheckedChange={async (checked) => {
                  const body = await run(() =>
                    conversionApi.save(org, { lock_balances: checked === true }),
                  );
                  if (body) setOverview(body);
                }}
              />
            )}
          </div>
        ) : null}

        {session && !finalised && current !== "date" && current !== "review" ? (
          <div className="flex gap-2">
            {index > 0 ? (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => void go(STEPS[index - 1] ?? "date")}
              >
                {fm(cm.back)}
              </Button>
            ) : null}
            <Button variant="primary" disabled={busy} onClick={next}>
              {fm(cm.next)}
            </Button>
          </div>
        ) : null}

        <div aria-live="polite" className="text-sm">
          {error ? (
            <p role="alert" className="text-fg-danger">
              {error}
            </p>
          ) : notice ? (
            <p className="text-fg-success">{notice}</p>
          ) : null}
        </div>
      </section>

      {session && renderMeter
        ? renderMeter({
            overview,
            rows: [...rows.bank, ...rows.other],
            readOnly: finalised,
            lockBalances: session.lock_balances,
            onFinalised: (body) => {
              setOverview(body);
              void loadLines();
            },
          })
        : null}
    </div>
  );
}
