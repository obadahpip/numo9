"use client";

/**
 * Manual journal screen (C-03-T11…T14), `/o/:org/accounting/journals/new`: the header (date,
 * journal type, narration, automatic reversal date), the lines (account, debit, credit,
 * description) and Post / Save as draft. As the journal is typed, the server is asked what it
 * would say (`journals/check`): problems are listed before posting.
 */
import { Button, ErrorState, Input } from "@numo9/ui";
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

  const submit = async (post: boolean) => {
    setBusy(true);
    setFailed(false);
    setRefusal(null);
    const result = await writeApi.create(org, { ...input, post });
    setBusy(false);
    if (result.status === 201) {
      const href = `/o/${org}/accounting/journals/${result.body.id}`;
      if (navigate) navigate(href);
      else window.location.assign(href);
      return;
    }
    if (result.status === 400 || result.status === 409) setRefusal(result.body);
    else setFailed(true);
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
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
      {failed ? (
        <p role="alert" className="text-sm text-fg-danger">
          {fm(wm.failed)}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <Button type="submit" disabled={busy || !accounts}>
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
    </form>
  );
}
