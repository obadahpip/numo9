"use client";

/**
 * Score card and grouped findings of the Assurance page (K-09-T21): the score with the open
 * counts by severity, then one collapsible group per rule (most severe first) whose items show
 * the plain-language explanation with its numbers, the amount, and the actions View source /
 * Propose fix / Acknowledge / Mark false positive (Reopen for an acknowledged item).
 */
import {
  Badge,
  Button,
  ChevronDownIcon,
  formatMoney,
  type AppLocale,
  type BadgeTone,
} from "@numo9/ui";
import Link from "next/link";
import { useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import type { Finding, Severity, Summary } from "./api";
import { scoreTone, type FindingGroup } from "./grouping";
import { am } from "./messages";

export type FindingAction = "fix" | "acknowledge" | "falsePositive" | "reopen";

const SCORE_CLASSES = {
  success: "text-fg-success",
  warning: "text-fg-warning",
  danger: "text-fg-danger",
} as const;

const SEVERITY_TONES: Record<Severity, BadgeTone> = {
  critical: "danger",
  warning: "warning",
  info: "info",
};

export function ScoreCard({ summary }: { summary: Summary }) {
  const fm = useFormatMessage();
  const tone = SCORE_CLASSES[scoreTone(summary.score)];
  return (
    <section
      aria-label={fm(am.score)}
      className="flex flex-wrap items-center gap-4 rounded-md border border-border bg-surface p-4"
      data-assurance-score={summary.score}
    >
      <div className="flex flex-col">
        <span className="text-sm text-fg-muted">{fm(am.score)}</span>
        <span className={`text-3xl font-semibold ${tone}`}>
          {fm(am.scoreValue, { score: summary.score })}
        </span>
      </div>
      <ul className="flex flex-wrap gap-2">
        {(["critical", "warning", "info"] as const).map((severity) => (
          <li key={severity}>
            <Badge tone={SEVERITY_TONES[severity]} dot>
              {fm(am.count, { severity, count: summary.open[severity] })}
            </Badge>
          </li>
        ))}
        <li>
          <Badge tone="neutral">
            {fm(am.acknowledgedCount, { count: summary.statuses.acknowledged })}
          </Badge>
        </li>
      </ul>
    </section>
  );
}

function Item({
  org,
  finding,
  locale,
  onAction,
}: {
  org: string;
  finding: Finding;
  locale: AppLocale;
  onAction: (action: FindingAction, finding: Finding) => void;
}) {
  const fm = useFormatMessage();
  const acknowledged = finding.status === "acknowledged";
  return (
    <li
      className="flex flex-col gap-2 border-t border-border py-3 first:border-t-0"
      data-finding={finding.id}
      data-status={finding.status}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="max-w-3xl text-sm text-fg">{finding.explanation}</p>
        {finding.amount !== null ? (
          <span className="font-mono text-sm tabular-nums text-fg" data-finding-amount="">
            {formatMoney(finding.amount, { locale, currency: "CAD" })}
          </span>
        ) : null}
      </div>
      {acknowledged && finding.ack_by ? (
        <p className="text-xs text-fg-muted">
          {finding.reason
            ? fm(am.ackByReason, { name: finding.ack_by.name, reason: finding.reason })
            : fm(am.ackBy, { name: finding.ack_by.name })}
        </p>
      ) : null}
      {finding.fix_entry ? <p className="text-xs text-fg-muted">{fm(am.fixDrafted)}</p> : null}
      <div className="flex flex-wrap gap-2">
        {finding.source ? (
          <Link
            href={`/o/${org}/${finding.source.path}`}
            className="inline-flex items-center rounded-md border border-border px-3 py-1 text-sm text-fg-accent-strong hover:bg-surface-muted"
          >
            {fm(am.viewSource)}
          </Link>
        ) : null}
        {finding.has_fix ? (
          <Button size="sm" variant="secondary" onClick={() => onAction("fix", finding)}>
            {fm(am.proposeFix)}
          </Button>
        ) : null}
        {acknowledged ? (
          <Button size="sm" variant="ghost" onClick={() => onAction("reopen", finding)}>
            {fm(am.reopen)}
          </Button>
        ) : (
          <Button size="sm" variant="ghost" onClick={() => onAction("acknowledge", finding)}>
            {fm(am.acknowledge)}
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => onAction("falsePositive", finding)}>
          {fm(am.falsePositive)}
        </Button>
      </div>
    </li>
  );
}

function Group({
  org,
  group,
  locale,
  onAction,
}: {
  org: string;
  group: FindingGroup;
  locale: AppLocale;
  onAction: (action: FindingAction, finding: Finding) => void;
}) {
  const fm = useFormatMessage();
  const id = useId();
  const [open, setOpen] = useState(true);
  return (
    <section
      className="rounded-md border border-border bg-surface"
      data-rule-group={group.rule}
      aria-labelledby={`${id}-heading`}
    >
      <h2 id={`${id}-heading`} className="text-base font-semibold text-fg">
        <button
          type="button"
          className="flex w-full items-center gap-3 px-4 py-3 text-start"
          aria-expanded={open}
          aria-controls={`${id}-items`}
          onClick={() => setOpen(!open)}
        >
          <span aria-hidden="true" className={open ? "" : "-rotate-90"}>
            <ChevronDownIcon />
          </span>
          <span className="flex-1">{group.name}</span>
          <Badge tone={SEVERITY_TONES[group.severity]}>
            {fm(am.severity, { severity: group.severity })}
          </Badge>
          <span className="text-sm font-normal text-fg-muted">
            {fm(am.groupCount, { count: group.findings.length })}
          </span>
        </button>
      </h2>
      {open ? (
        <ul id={`${id}-items`} className="px-4 pb-2">
          {group.findings.map((finding) => (
            <Item
              key={finding.id}
              org={org}
              finding={finding}
              locale={locale}
              onAction={onAction}
            />
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export function AssuranceFindings({
  org,
  groups,
  locale,
  onAction,
}: {
  org: string;
  groups: FindingGroup[];
  locale: AppLocale;
  onAction: (action: FindingAction, finding: Finding) => void;
}) {
  return (
    <div className="flex flex-col gap-3" data-assurance-groups={groups.length}>
      {groups.map((group) => (
        <Group key={group.rule} org={org} group={group} locale={locale} onAction={onAction} />
      ))}
    </div>
  );
}
