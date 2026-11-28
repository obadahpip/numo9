"use client";

/**
 * Assurance (K-09-T21), `/o/:org/accounting/assurance`: the score card, severity filter chips,
 * a status filter and a text search, then the findings grouped by rule with their plain-language
 * explanation and the actions View source / Propose fix / Acknowledge / Mark false positive.
 * *Run the rules* starts a full run in the background and refreshes the list after it. Propose fix
 * opens the proposed-fix drawer (K-09-T22, `FixDrawer`): the reasoning and an editable draft
 * journal that becomes a draft in Journals › Draft; a recode fix opens Find & recode. Tabs
 * (`?tab=`): *Findings*, *Rule settings* (K-09-T23, `RuleSettings`) and *Activity* (K-09-T24,
 * `ActivityHeatmap`); every summary loaded updates the nav badge (`announceSummary`).
 */
import {
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  INPUT_BASE,
  Tabs,
  formatDate,
  type AppLocale,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { assuranceApi, type Finding, type FindingStatus, type Severity, type Summary } from "./api";
import { AssuranceFindings, ScoreCard, type FindingAction } from "./AssuranceFindings";
import { announceSummary } from "./badge";
import { FixDrawer } from "./FixDrawer";
import { ActivityHeatmap } from "./Heatmap";
import { groupFindings, SEVERITIES } from "./grouping";
import { am } from "./messages";
import { RuleSettings } from "./RuleSettings";
import { isAssuranceTab, type AssuranceTab } from "./tabs";

const STATUSES: readonly ("" | FindingStatus)[] = [
  "",
  "open",
  "acknowledged",
  "resolved",
  "false_positive",
];
const REFRESH_MS = 4000;

export function AssuranceScreen({
  org,
  initialTab = "findings",
}: {
  org: string;
  initialTab?: AssuranceTab;
}) {
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
  const [tab, setTab] = useState<AssuranceTab>(initialTab);

  const load = useCallback(async () => {
    const [s, f] = await Promise.all([
      assuranceApi.summary(org).catch(() => null),
      assuranceApi
        .findings(org, { severity: severities, status: status ? [status] : [], q: text })
        .catch(() => null),
    ]);
    if (s?.status === 200 && f?.status === 200) {
      setSummary(s.body);
      announceSummary(org, s.body);
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
      <Tabs
        label={fm(am.tabs)}
        value={tab}
        onValueChange={(value) => {
          if (!isAssuranceTab(value)) return;
          setTab(value);
          const url = new URL(window.location.href);
          if (value === "findings") url.searchParams.delete("tab");
          else url.searchParams.set("tab", value);
          window.history.replaceState(null, "", url.toString());
          if (value === "findings") void load();
        }}
        items={[
          {
            value: "findings",
            label: fm(am.tabFindings),
            content: (
              <div className="flex flex-col gap-4 pt-4">
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
              </div>
            ),
          },
          {
            value: "rules",
            label: fm(am.tabRules),
            content:
              tab === "rules" ? (
                <div className="pt-4">
                  <RuleSettings org={org} />
                </div>
              ) : null,
          },
          {
            value: "activity",
            label: fm(am.tabActivity),
            content:
              tab === "activity" ? (
                <div className="pt-4">
                  <ActivityHeatmap org={org} locale={locale} />
                </div>
              ) : null,
          },
        ]}
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
      <FixDrawer
        org={org}
        locale={locale}
        finding={fixFor}
        onClose={() => setFixFor(null)}
        onDrafted={() => {
          setNotice(fm(am.draftCreated));
          void load();
        }}
      />
    </div>
  );
}
