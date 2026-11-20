"use client";

/**
 * Manual journal screen (C-03-T11…T14), `/o/:org/accounting/journals/new`: the header (date,
 * journal type, narration, automatic reversal date), the lines (account, debit, credit,
 * description) and Post / Save as draft. As the journal is typed, the server is asked what it
 * would say (`journals/check`): problems are listed before posting.
 */
import { Button, Dialog, ErrorState, Input } from "@numo9/ui";
import { useEffect, useId, useMemo, useState, type FormEvent } from "react";

import { accountsApi, type Account } from "@/accounts/api";
import { useDebounced } from "@/directory/useDebounced";
import { useFormatMessage } from "@/i18n";

import {
  filledLines,
  writeApi,
  type CheckResult,
  type JournalInput,
  type JournalTypeKey,
  type LineInput,
  type Refusal,
} from "./api";
import { JournalTypePicker } from "./JournalTypePicker";
import { wm } from "./messages";

export const CHECK_DEBOUNCE_MS = 400;
/** The shortest reason an adviser may give to post below zero (server rule, C-03-T08). */
export const MIN_OVERRIDE_REASON = 10;

const emptyLine = (): LineInput => ({
  account: "",
  debit: "",
  credit: "",
  book: "both",
  contact: null,
  description: "",
});

const today = () => new Date().toISOString().slice(0, 10);

function money(lines: LineInput[], side: "debit" | "credit"): string {
  const cents = lines.reduce((sum, line) => sum + Math.round(Number(line[side] || 0) * 100), 0);
  return (cents / 100).toFixed(2);
}

export interface JournalFormProps {
  org: string;
  /** Where a posted or saved journal opens (default: its page). */
  navigate?: (href: string) => void;
}

export function JournalForm({ org, navigate }: Readonly<JournalFormProps>) {
  const fm = useFormatMessage();
  const headingId = useId();
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [date, setDate] = useState(today);
  const [journalType, setJournalType] = useState<JournalTypeKey>("general");
  const [narration, setNarration] = useState("");
  const [autoReverse, setAutoReverse] = useState("");
  const [lines, setLines] = useState<LineInput[]>([emptyLine(), emptyLine()]);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [reason, setReason] = useState("");
  const reasonId = useId();

  useEffect(() => {
    accountsApi
      .list(org, "active")
      .then((result) => {
        if (result.status === 200) setAccounts(result.body.results.filter((a) => !a.has_children));
        else setLoadFailed(true);
      })
      .catch(() => setLoadFailed(true));
  }, [org]);

  const input: JournalInput = useMemo(
    () => ({
      date,
      journal_type: journalType,
      narration,
      auto_reverse_on: autoReverse || null,
      lines: filledLines(lines),
      attachments: [],
    }),
    [date, journalType, narration, autoReverse, lines],
  );
  const asked = useDebounced(input, CHECK_DEBOUNCE_MS);

  useEffect(() => {
    if (asked.lines.length < 2) {
      setCheck(null);
      return;
    }
    let current = true;
    writeApi
      .check(org, asked)
      .then((result) => {
        if (current && result.status === 200) setCheck(result.body);
      })
      .catch(() => undefined);
    return () => {
      current = false;
    };
  }, [org, asked]);

  const setLine = (index: number, changes: Partial<LineInput>) =>
    setLines((rows) => rows.map((row, i) => (i === index ? { ...row, ...changes } : row)));

  const submit = async (post: boolean, overrideReason = "") => {
    setBusy(true);
    setFailed(false);
    setRefusal(null);
    const body = overrideReason
      ? { ...input, post, override_reason: overrideReason }
      : { ...input, post };
    const result = await writeApi.create(org, body);
    setBusy(false);
    if (result.status === 201) {
      const href = `/o/${org}/accounting/journals/${result.body.id}`;
      if (navigate) navigate(href);
      else window.location.assign(href);
      return;
    }
    if (result.status === 409 && result.body.code === "ledger.journal.override_reason_required") {
      setOverrideOpen(true);
      setCheck((c) =>
        c ? { ...c, adviser: true, shortfalls: result.body.shortfalls ?? c.shortfalls } : c,
      );
      return;
    }
    if (result.status === 400 || result.status === 409) setRefusal(result.body);
    else setFailed(true);
  };

  const shortfalls = refusal?.shortfalls ?? check?.shortfalls ?? [];
  const adviser = refusal?.adviser ?? check?.adviser ?? false;
  const blocked = shortfalls.length > 0 && !adviser;

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (blocked) return;
    if (shortfalls.length > 0 && adviser) {
      setOverrideOpen(true);
      return;
    }
    void submit(true);
  };

  if (loadFailed)
    return (
      <ErrorState
        title={fm(wm.failed)}
        retryLabel={fm(wm.retry)}
        onRetry={() => window.location.reload()}
      />
    );
  const problems = refusal?.errors ?? check?.errors ?? [];
  const chipFor = (accountId: string) =>
    shortfalls.find((shortfall) => shortfall.account.id === accountId)?.message;

  return (
    <form
      aria-labelledby={headingId}
      onSubmit={onSubmit}
      className="flex max-w-5xl flex-col gap-6 p-4"
      noValidate
    >
      <h1 id={headingId} className="text-2xl font-semibold text-fg">
        {fm(wm.title)}
      </h1>
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(wm.date)}
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-fg sm:col-span-2">
          {fm(wm.narration)}
          <Input value={narration} onChange={(e) => setNarration(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(wm.autoReverse)}
          <Input type="date" value={autoReverse} onChange={(e) => setAutoReverse(e.target.value)} />
        </label>
      </div>
      <JournalTypePicker value={journalType} onChange={setJournalType} />

      <table className="w-full text-sm">
        <caption className="pb-2 text-start text-lg font-semibold text-fg">{fm(wm.lines)}</caption>
        <thead>
          <tr className="text-start text-xs text-fg-muted">
            <th scope="col" className="w-2/5 py-1 text-start">
              {fm(wm.account)}
            </th>
            <th scope="col" className="py-1 text-end">
              {fm(wm.debit)}
            </th>
            <th scope="col" className="py-1 text-end">
              {fm(wm.credit)}
            </th>
            <th scope="col" className="py-1 text-start">
              {fm(wm.description)}
            </th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line, index) => {
            const n = index + 1;
            return (
              <tr key={index} className="border-t border-border align-top" data-line={n}>
                <td className="py-2 pe-2">
                  <select
                    aria-label={fm(wm.accountOfLine, { line: n })}
                    value={line.account}
                    onChange={(e) => setLine(index, { account: e.target.value })}
                    className="min-h-touch-target w-full rounded-md border border-border bg-surface px-2 text-sm text-fg"
                  >
                    <option value="">{fm(wm.chooseAccount)}</option>
                    {(accounts ?? []).map((account) => (
                      <option key={account.id} value={account.id}>
                        {fm(wm.accountOption, { code: account.code, name: account.name })}
                      </option>
                    ))}
                  </select>
                  {line.account && chipFor(line.account) ? (
                    <p
                      data-chip="negative-cash"
                      className="mt-1 inline-flex rounded-full bg-surface-danger-subtle px-2 py-0.5 text-xs font-medium text-fg-danger"
                    >
                      {chipFor(line.account)}
                    </p>
                  ) : null}
                </td>
                <td className="py-2 pe-2">
                  <Input
                    numeric
                    inputMode="decimal"
                    aria-label={fm(wm.debitOfLine, { line: n })}
                    value={line.debit}
                    onChange={(e) => setLine(index, { debit: e.target.value, credit: "" })}
                  />
                </td>
                <td className="py-2 pe-2">
                  <Input
                    numeric
                    inputMode="decimal"
                    aria-label={fm(wm.creditOfLine, { line: n })}
                    value={line.credit}
                    onChange={(e) => setLine(index, { credit: e.target.value, debit: "" })}
                  />
                </td>
                <td className="py-2">
                  <Input
                    aria-label={fm(wm.descriptionOfLine, { line: n })}
                    value={line.description}
                    onChange={(e) => setLine(index, { description: e.target.value })}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Button
          variant="secondary"
          type="button"
          onClick={() => setLines((r) => [...r, emptyLine()])}
        >
          {fm(wm.addLine)}
        </Button>
        <p className="text-sm text-fg-muted" data-totals="">
          {fm(wm.totals, { debit: money(lines, "debit"), credit: money(lines, "credit") })}
        </p>
      </div>

      {problems.length ? (
        <section
          aria-labelledby={`${headingId}-problems`}
          className="rounded-md border border-border-danger p-3"
        >
          <h2 id={`${headingId}-problems`} className="text-sm font-semibold text-fg-danger">
            {fm(wm.problems)}
          </h2>
          <ul className="mt-1 list-disc ps-5 text-sm text-fg">
            {problems.map((problem, i) => (
              <li key={`${problem.code}-${i}`} data-code={problem.code}>
                {problem.message}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {blocked ? (
        <p role="alert" className="text-sm font-medium text-fg-danger" data-blocked="">
          {fm(wm.blocked)}
        </p>
      ) : null}
      {failed ? (
        <p role="alert" className="text-sm text-fg-danger">
          {fm(wm.failed)}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={busy || !accounts || blocked}>
          {busy ? fm(wm.posting) : fm(wm.post)}
        </Button>
        <Button
          variant="secondary"
          type="button"
          disabled={busy}
          onClick={() => void submit(false)}
        >
          {fm(wm.saveDraft)}
        </Button>
      </div>
      <Dialog
        open={overrideOpen}
        onOpenChange={setOverrideOpen}
        title={fm(wm.overrideTitle)}
        description={fm(wm.overrideBody)}
        closeLabel={fm(wm.close)}
        footer={
          <>
            <Button variant="secondary" type="button" onClick={() => setOverrideOpen(false)}>
              {fm(wm.cancel)}
            </Button>
            <Button
              type="button"
              disabled={busy || reason.trim().length < MIN_OVERRIDE_REASON}
              onClick={() => {
                setOverrideOpen(false);
                void submit(true, reason.trim());
              }}
            >
              {fm(wm.overrideConfirm)}
            </Button>
          </>
        }
      >
        <ul className="mb-3 list-disc ps-5 text-sm text-fg-danger">
          {shortfalls.map((shortfall) => (
            <li key={shortfall.account.id}>{shortfall.message}</li>
          ))}
        </ul>
        <label htmlFor={reasonId} className="text-sm font-medium text-fg">
          {fm(wm.overrideReason, { min: MIN_OVERRIDE_REASON })}
        </label>
        <textarea
          id={reasonId}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          minLength={MIN_OVERRIDE_REASON}
          required
          className="mt-1 w-full rounded-md border border-border bg-surface p-2 text-sm text-fg"
        />
      </Dialog>
    </form>
  );
}
