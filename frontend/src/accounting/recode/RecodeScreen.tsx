"use client";

/**
 * Find & recode (C-07-T10 – T13), `/o/:org/accounting/recode`: two panes — the conditions on
 * the left (condition builder, C-07-T10), the lines found on the right (results grid with
 * select-all across pages and the Excluded tab, C-07-T11); then the new coding, the preview
 * diff and the confirm dialog with the numbers (C-07-T12). A recode of more than 200 lines runs
 * in the background: its progress shows in a status toast until it finishes. Below, the
 * history of recodes with Undo and the audit report (C-07-T13).
 */
import { Button, INPUT_BASE, useOptionalToast } from "@numo9/ui";
import { useCallback, useEffect, useRef, useState } from "react";

import { accountsApi } from "@/accounts/api";
import { useFormatMessage } from "@/i18n";

import {
  recodeApi,
  type Batch,
  type Criteria,
  type Match,
  type PreviewResult,
  type SearchResult,
} from "./api";
import { ConditionBuilder, type AccountOption } from "./ConditionBuilder";
import { emptyRows, newRow, serialise, type Row } from "./conditions";
import { rm } from "./messages";
import { BatchHistory } from "./BatchHistory";
import {
  ChangesForm,
  ConfirmRecode,
  EMPTY_CHANGES,
  RecodePreviewPanel,
  toChanges,
  type ChangesDraft,
} from "./RecodePreview";
import { RecodeResults } from "./RecodeResults";
import { chosen } from "./selection";

const POLL_MS = 1000;

export function RecodeScreen({ org }: { org: string }) {
  const fm = useFormatMessage();
  const [accounts, setAccounts] = useState<AccountOption[]>([]);
  const [match, setMatch] = useState<Match>("all");
  const [rows, setRows] = useState<Row[]>(() => [newRow("account")]);
  const [invalid, setInvalid] = useState<string[]>([]);
  const [criteria, setCriteria] = useState<Criteria | null>(null);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<ChangesDraft>(EMPTY_CHANGES);
  const [noChanges, setNoChanges] = useState(false);
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [name, setName] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [running, setRunning] = useState<Batch | null>(null);
  const [notice, setNotice] = useState("");
  const [history, setHistory] = useState(0);
  const toast = useOptionalToast();
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  useEffect(() => {
    void accountsApi
      .list(org, "active")
      .then((answer) => {
        if (answer.status === 200) {
          setAccounts(
            answer.body.results.map((a) => ({ id: a.id, label: `${a.code} · ${a.name}` })),
          );
        }
      })
      .catch(() => undefined);
  }, [org]);

  const run = useCallback(
    async (search: Criteria, page: number) => {
      setBusy(true);
      setError("");
      const answer = await recodeApi.search(org, search, page).catch(() => null);
      setBusy(false);
      if (answer?.status === 200) {
        setResult(answer.body);
        return true;
      }
      setError(answer?.body?.detail || fm(rm.failed));
      return false;
    },
    [org, fm],
  );

  const search = async () => {
    const missing = emptyRows(rows);
    setInvalid(missing);
    if (missing.length) return;
    const next = serialise(match, rows);
    setCriteria(next);
    setSelected(new Set());
    setPreview(null);
    await run(next, 1);
  };

  const selection = () => {
    if (!result) return null;
    const all = result.keys;
    return selected.size === 0 || selected.size === all.length ? null : chosen(all, selected);
  };

  const showPreview = async () => {
    const changes = toChanges(draft);
    setNoChanges(!changes);
    if (!changes || !criteria) return;
    setBusy(true);
    setError("");
    const answer = await recodeApi.preview(org, criteria, changes, selection()).catch(() => null);
    setBusy(false);
    if (answer?.status === 200) setPreview(answer.body);
    else setError(answer?.body?.detail || fm(rm.failed));
  };

  const finished = (batch: Batch) => {
    setRunning(null);
    const text = fm(rm.done, { lines: batch.line_count, problems: batch.problem_count });
    setNotice(text);
    toast?.toast({ title: text, tone: "success" });
    setPreview(null);
    setSelected(new Set());
    setHistory((n) => n + 1);
    if (criteria) void run(criteria, 1);
  };

  const follow = (batch: Batch) => {
    setRunning(batch);
    timer.current = setTimeout(() => {
      void recodeApi
        .batch(org, batch.id)
        .then((answer) => {
          if (answer.status !== 200) return follow(batch);
          if (answer.body.status === "running") return follow(answer.body);
          return finished(answer.body);
        })
        .catch(() => follow(batch));
    }, POLL_MS);
  };

  const execute = async () => {
    const changes = toChanges(draft);
    if (!changes || !criteria || !preview) return;
    setBusy(true);
    setError("");
    const answer = await recodeApi
      .execute(org, {
        criteria,
        changes,
        selection: selection(),
        name: name.trim(),
        confirm_tax: preview.summary.needs_confirmation,
      })
      .catch(() => null);
    setBusy(false);
    setConfirming(false);
    if (answer?.status === 201) finished(answer.body);
    else if (answer?.status === 202) follow(answer.body);
    else setError(answer?.body?.detail || fm(rm.failed));
  };

  return (
    <div className="flex flex-col gap-4" data-recode="">
      <header>
        <h1 className="text-xl font-semibold text-fg">{fm(rm.title)}</h1>
        <p className="max-w-3xl text-sm text-fg-muted">{fm(rm.intro)}</p>
      </header>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <p role="status" className="text-sm text-fg-success">
        {notice}
      </p>
      {running ? (
        <div
          role="status"
          className="fixed bottom-4 end-4 z-50 rounded-md border border-border bg-surface p-3 text-sm shadow-lg"
          data-recode-progress=""
        >
          {fm(rm.running, { done: running.progress, total: running.line_count })}
        </div>
      ) : null}
      <div className="flex flex-col gap-6 lg:flex-row">
        <aside className="flex w-full flex-col gap-3 lg:w-96 lg:shrink-0">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void search();
            }}
            className="flex flex-col gap-3"
          >
            <ConditionBuilder
              match={match}
              rows={rows}
              accounts={accounts}
              onMatchChange={setMatch}
              onRowsChange={setRows}
              invalid={invalid}
            />
            <div>
              <Button type="submit" variant="primary" disabled={busy}>
                {fm(rm.search)}
              </Button>
            </div>
          </form>
        </aside>
        <section className="flex min-w-0 flex-1 flex-col gap-4">
          {result && criteria ? (
            <RecodeResults
              result={result}
              selected={selected}
              onSelectedChange={(next) => {
                setSelected(next);
                setPreview(null);
              }}
              onPage={(page) => void run(criteria, page)}
            />
          ) : null}
          {result && result.count > 0 ? (
            <div className="flex flex-col gap-3">
              <ChangesForm
                draft={draft}
                accounts={accounts}
                onChange={(next) => {
                  setDraft(next);
                  setPreview(null);
                }}
              />
              {noChanges ? (
                <p role="alert" className="text-sm text-fg-danger">
                  {fm(rm.noChanges)}
                </p>
              ) : null}
              <div>
                <Button variant="secondary" disabled={busy} onClick={() => void showPreview()}>
                  {fm(rm.previewButton)}
                </Button>
              </div>
            </div>
          ) : null}
          {preview ? (
            <>
              <RecodePreviewPanel preview={preview} accounts={accounts} />
              <div className="flex flex-wrap items-end gap-3">
                <label className="flex flex-col gap-1 text-sm text-fg">
                  {fm(rm.batchName)}
                  <input
                    className={`${INPUT_BASE} border-border`}
                    value={name}
                    maxLength={200}
                    onChange={(event) => setName(event.target.value)}
                  />
                </label>
                <Button
                  variant="primary"
                  disabled={busy || preview.summary.lines === 0 || Boolean(running)}
                  onClick={() => setConfirming(true)}
                >
                  {fm(rm.recode, { count: preview.summary.lines })}
                </Button>
              </div>
              <ConfirmRecode
                open={confirming}
                onOpenChange={setConfirming}
                preview={preview}
                busy={busy}
                onConfirm={() => void execute()}
              />
            </>
          ) : null}
        </section>
      </div>
      <BatchHistory org={org} refresh={history} />
    </div>
  );
}
