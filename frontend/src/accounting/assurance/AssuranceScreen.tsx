"use client";

/**
 * Assurance (K-09-T21), `/o/:org/accounting/assurance`: the score card, severity filter chips,
 * a status filter and a text search, then the findings grouped by rule with their plain-language
 * explanation and the actions View source / Propose fix / Acknowledge / Mark false positive.
 * *Run the rules* starts a full run in the background and refreshes the list after it. Propose fix
 * shows the proposed entry with its reasoning and turns it into a draft journal (the editable
 * drawer is K-09-T22); a recode fix opens Find & recode.
 */
import {
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  INPUT_BASE,
  formatDate,
  formatMoney,
  sumDecimals,
  type AppLocale,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useState } from "react";

import { useFormatMessage } from "@/i18n";

import {
  assuranceApi,
  type Finding,
  type FindingStatus,
  type Fix,
  type Severity,
  type Summary,
} from "./api";
import { AssuranceFindings, ScoreCard, type FindingAction } from "./AssuranceFindings";
import { groupFindings, SEVERITIES } from "./grouping";
import { am } from "./messages";

const STATUSES: readonly ("" | FindingStatus)[] = [
  "",
  "open",
  "acknowledged",
  "resolved",
  "false_positive",
];
const REFRESH_MS = 4000;

export function AssuranceScreen({ org }: { org: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [severities, setSeverities] = useState<Severity[]>([]);
  const [status, setStatus] = useState<"" | FindingStatus>("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [falsePositive, setFalsePositive] = useState<Finding | null>(null);
  const [reason, setReason] = useState("");
  const [fixFor, setFixFor] = useState<Finding | null>(null);
  const [fix, setFix] = useState<Fix | null | undefined>(undefined);
  const [draft, setDraft] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [s, f] = await Promise.all([
      assuranceApi.summary(org).catch(() => null),
      assuranceApi
        .findings(org, { severity: severities, status: status ? [status] : [], q: text })
        .catch(() => null),
    ]);
    if (s?.status === 200 && f?.status === 200) {
      setSummary(s.body);
      setFindings(f.body.findings);
      setFailed(false);
    } else setFailed(true);
  }, [org, severities, status, text]);

  useEffect(() => {
    void load();
  }, [load]);

  const groups = useMemo(() => groupFindings(findings ?? []), [findings]);

  const toggle = (severity: Severity) =>
    setSeverities((current) =>
      current.includes(severity) ? current.filter((s) => s !== severity) : [...current, severity],
    );

  const runChecks = async () => {
    setBusy(true);
    setError("");
    const answer = await assuranceApi.run(org).catch(() => null);
    setBusy(false);
    if (answer?.status === 202) {
      setNotice(fm(am.running));
      setTimeout(() => void load(), REFRESH_MS);
    } else setError(answer?.body?.detail || fm(am.failed));
  };

  const act = async (action: FindingAction, finding: Finding) => {
    setError("");
    if (action === "falsePositive") {
      setReason("");
      setFalsePositive(finding);
      return;
    }
    if (action === "fix") {
      setFixFor(finding);
      setFix(undefined);
      setDraft(null);
      const answer = await assuranceApi.fix(org, finding.id).catch(() => null);
      setFix(answer?.status === 200 ? answer.body.fix : null);
      return;
    }
    const answer = await (
      action === "acknowledge"
        ? assuranceApi.acknowledge(org, finding.id)
        : assuranceApi.reopen(org, finding.id)
    ).catch(() => null);
    if (answer?.status === 200) await load();
    else setError(answer?.body?.detail || fm(am.failed));
  };

  const saveFalsePositive = async () => {
    if (!falsePositive) return;
    setBusy(true);
    const answer = await assuranceApi
      .falsePositive(org, falsePositive.id, reason.trim())
      .catch(() => null);
    setBusy(false);
    if (answer?.status === 200) {
      setFalsePositive(null);
      await load();
    } else setError(answer?.body?.detail || fm(am.failed));
  };

  const createDraft = async () => {
    if (!fixFor) return;
    setBusy(true);
    const answer = await assuranceApi.createFix(org, fixFor.id).catch(() => null);
    setBusy(false);
    if (answer?.status === 201) {
      setDraft(answer.body.draft.id);
      setNotice(fm(am.draftCreated));
      await load();
    } else setError(answer?.body?.detail || fm(am.failed));
  };

  const money = (value: string) => formatMoney(value, { locale, currency: "CAD" });

  return (
    <div className="flex flex-col gap-4" data-assurance="">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-fg">{fm(am.title)}</h1>
          <p className="max-w-3xl text-sm text-fg-muted">{fm(am.intro)}</p>
          <p className="text-xs text-fg-muted">
            {summary?.last_run
              ? fm(am.lastRun, {
                  when: formatDate(new Date(summary.last_run.started_at), { locale }),
                })
              : fm(am.neverRun)}
          </p>
        </div>
        <Button variant="primary" disabled={busy} onClick={() => void runChecks()}>
          {fm(am.run)}
        </Button>
      </header>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <p role="status" className="text-sm text-fg-success">
        {notice}
      </p>
      {failed ? (
        <ErrorState
          title={fm(am.loadFailed)}
          retryLabel={fm(am.retry)}
          onRetry={() => void load()}
        />
      ) : null}
      {summary ? <ScoreCard summary={summary} /> : null}
      <div
        role="group"
        aria-label={fm(am.filters)}
        className="flex flex-wrap items-end gap-3"
        data-assurance-filters=""
      >
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            aria-pressed={severities.length === 0}
            className="rounded-full border border-border px-3 py-1 text-sm aria-pressed:bg-surface-accent-subtle"
            onClick={() => setSeverities([])}
          >
            {fm(am.allSeverities)}
          </button>
          {SEVERITIES.map((severity) => (
            <button
              key={severity}
              type="button"
              aria-pressed={severities.includes(severity)}
              className="rounded-full border border-border px-3 py-1 text-sm aria-pressed:bg-surface-accent-subtle"
              onClick={() => toggle(severity)}
              data-severity-chip={severity}
            >
              {summary
                ? fm(am.count, { severity, count: summary.open[severity] })
                : fm(am.severity, { severity })}
            </button>
          ))}
        </div>
        <label className="flex flex-col gap-1 text-sm text-fg" htmlFor={`${ids}-status`}>
          {fm(am.statusLabel)}
          <select
            id={`${ids}-status`}
            className={`${INPUT_BASE} border-border`}
            value={status}
            onChange={(event) => setStatus(event.target.value as "" | FindingStatus)}
          >
            {STATUSES.map((value) => (
              <option key={value || "active"} value={value}>
                {fm(am.status, { status: value || "active" })}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm text-fg" htmlFor={`${ids}-q`}>
          {fm(am.search)}
          <input
            id={`${ids}-q`}
            type="search"
            className={`${INPUT_BASE} border-border`}
            placeholder={fm(am.searchPlaceholder)}
            value={text}
            onChange={(event) => setText(event.target.value)}
          />
        </label>
      </div>
      {findings && groups.length === 0 && !failed ? (
        <EmptyState title={fm(am.emptyTitle)} body={fm(am.emptyBody)} />
      ) : null}
      <AssuranceFindings
        org={org}
        groups={groups}
        locale={locale}
        onAction={(action, finding) => void act(action, finding)}
      />
      <Dialog
        open={falsePositive !== null}
        onOpenChange={(open) => (open ? null : setFalsePositive(null))}
        title={fm(am.falsePositiveTitle)}
        description={fm(am.falsePositiveHelp)}
        closeLabel={fm(am.close)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setFalsePositive(null)}>
              {fm(am.cancel)}
            </Button>
            <Button
              variant="primary"
              disabled={busy || reason.trim().length < 5}
              onClick={() => void saveFalsePositive()}
            >
              {fm(am.save)}
            </Button>
          </>
        }
      >
        <label className="flex flex-col gap-1 text-sm text-fg" htmlFor={`${ids}-reason`}>
          {fm(am.reason)}
          <textarea
            id={`${ids}-reason`}
            className={`${INPUT_BASE} border-border`}
            value={reason}
            maxLength={2000}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
      </Dialog>
      <Dialog
        open={fixFor !== null}
        onOpenChange={(open) => (open ? null : setFixFor(null))}
        title={fm(am.fixTitle)}
        closeLabel={fm(am.close)}
        size="lg"
        footer={
          fix?.kind === "journal" && !draft ? (
            <>
              <Button variant="secondary" onClick={() => setFixFor(null)}>
                {fm(am.cancel)}
              </Button>
              <Button variant="primary" disabled={busy} onClick={() => void createDraft()}>
                {fm(am.createDraft)}
              </Button>
            </>
          ) : null
        }
      >
        {fix === null ? <p className="text-sm text-fg">{fm(am.noFix)}</p> : null}
        {fix ? (
          <div className="flex flex-col gap-3" data-fix-kind={fix.kind}>
            <h3 className="text-sm font-semibold text-fg">{fm(am.fixWhy)}</h3>
            <p className="text-sm text-fg">{fix.reasoning}</p>
            {fix.kind === "journal" ? (
              <>
                {fix.date ? (
                  <p className="text-sm text-fg-muted">
                    {fm(am.fixDate, { date: formatDate(fix.date, { locale }) })}
                  </p>
                ) : null}
                <table className="w-full text-sm" data-fix-lines="">
                  <thead>
                    <tr className="text-start text-fg-muted">
                      <th scope="col" className="text-start">
                        {fm(am.account)}
                      </th>
                      <th scope="col" className="text-end">
                        {fm(am.debit)}
                      </th>
                      <th scope="col" className="text-end">
                        {fm(am.credit)}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {fix.lines.map((line) => (
                      <tr key={`${line.account}-${line.debit}-${line.credit}`}>
                        <td>{line.label}</td>
                        <td className="text-end tabular-nums">
                          {Number(line.debit) ? money(line.debit) : ""}
                        </td>
                        <td className="text-end tabular-nums">
                          {Number(line.credit) ? money(line.credit) : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-sm text-fg-muted">
                  {fm(am.totals, {
                    debit: money(sumDecimals(fix.lines.map((l) => l.debit))),
                    credit: money(sumDecimals(fix.lines.map((l) => l.credit))),
                  })}
                </p>
                {fix.alternatives.map((alternative) => (
                  <p key={alternative.reasoning} className="text-sm text-fg-muted">
                    {fm(am.alternatives, { text: alternative.reasoning })}
                  </p>
                ))}
                {draft ? (
                  <Link
                    href={`/o/${org}/accounting/journals/${draft}`}
                    className="text-sm text-fg-accent-strong underline"
                  >
                    {fm(am.openDraft)}
                  </Link>
                ) : null}
              </>
            ) : (
              <Link
                href={`/o/${org}/accounting/recode`}
                className="text-sm text-fg-accent-strong underline"
              >
                {fm(am.openRecode)}
              </Link>
            )}
          </div>
        ) : null}
      </Dialog>
    </div>
  );
}
