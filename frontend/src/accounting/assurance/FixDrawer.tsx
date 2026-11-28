"use client";

/**
 * Proposed-fix drawer (K-09-T22, wireframe A3): the rule's reasoning ("Why this entry"), then the
 * proposed correcting entry as an **editable** draft journal — date, narration and a grid of
 * account (the journal account picker), debit, credit and description, with totals and the
 * out-of-balance message — and the other options the rule offers (*Use this option* loads one
 * into the grid). *Create draft journal* sends the edited lines (`POST …/fix`): the entry is saved
 * as a **draft**, never posted, and the drawer links to it and to Journals › Draft. A recode fix
 * (EXEMPT_ON_TAXABLE_ACCOUNT) shows the suggested change and opens Find & recode instead.
 */
import {
  AccountPicker,
  Button,
  CloseIcon,
  Drawer,
  formatDate,
  formatMoney,
  Input,
  type AppLocale,
} from "@numo9/ui";
import Link from "next/link";
import { useEffect, useId, useMemo, useState } from "react";

import { accountsApi, type Account } from "@/accounts/api";
import { pickerAccount } from "@/accounts/picker";
import { useDocumentLinesLabels } from "@/documents/labels";
import { useFormatMessage } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

import { assuranceApi, type Finding, type Fix } from "./api";
import {
  emptyGridLine,
  gridFromFix,
  gridPayload,
  gridProblem,
  gridTotals,
  type GridLine,
} from "./fixGrid";
import { am } from "./messages";

export interface FixDrawerProps {
  org: string;
  locale: AppLocale;
  /** The finding whose fix is shown; `null` closes the drawer. */
  finding: Finding | null;
  onClose: () => void;
  /** After the draft is created (the page reloads its findings). */
  onDrafted: (draftId: string) => void;
}

export function FixDrawer({ org, locale, finding, onClose, onDrafted }: FixDrawerProps) {
  const fm = useFormatMessage();
  const ids = useId();
  const { accountTypes, noAccounts } = useDocumentLinesLabels();
  const [fix, setFix] = useState<Fix | null | undefined>(undefined);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [lines, setLines] = useState<GridLine[]>([]);
  const [date, setDate] = useState("");
  const [narration, setNarration] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState<string | null>(null);

  useEffect(() => {
    if (!finding) return;
    let cancelled = false;
    setFix(undefined);
    setDraft(null);
    setError("");
    void assuranceApi
      .fix(org, finding.id)
      .catch(() => null)
      .then((answer) => {
        if (cancelled) return;
        const found = answer?.status === 200 ? answer.body.fix : null;
        setFix(found);
        if (found?.kind === "journal") {
          setLines(gridFromFix(found));
          setDate(found.date ?? "");
          setNarration(found.narration);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [org, finding]);

  useEffect(() => {
    if (!finding || accounts.length) return;
    void accountsApi
      .list(org, "active")
      .then((answer) => {
        if (answer.status === 200) setAccounts(answer.body.results.filter((a) => !a.has_children));
      })
      .catch(() => undefined);
  }, [org, finding, accounts.length]);

  const pickerAccounts = useMemo(() => accounts.map(pickerAccount), [accounts]);
  const totals = gridTotals(lines);
  const problem = gridProblem(lines);
  const money = (value: string) => formatMoney(value, { locale, currency: "CAD" });

  const setLine = (key: number, changes: Partial<GridLine>) =>
    setLines((current) => current.map((l) => (l.key === key ? { ...l, ...changes } : l)));

  const applyAlternative = (alternative: Fix) => {
    setLines(gridFromFix(alternative));
    if (alternative.date) setDate(alternative.date);
    if (alternative.narration) setNarration(alternative.narration);
  };

  const create = async () => {
    if (!finding || problem) return;
    setBusy(true);
    setError("");
    const answer = await assuranceApi
      .createFix(org, finding.id, {
        lines: gridPayload(lines),
        ...(date ? { date } : {}),
        narration: narration.trim(),
      })
      .catch(() => null);
    setBusy(false);
    if (answer?.status === 201) {
      setDraft(answer.body.draft.id);
      onDrafted(answer.body.draft.id);
    } else setError(answer?.body?.detail || fm(am.failed));
  };

  const journal = fix?.kind === "journal";
  const journalsUrl = orgModuleUrl(org, "accounting/journals");

  return (
    <Drawer
      open={finding !== null}
      onOpenChange={(open) => (open ? null : onClose())}
      title={fm(am.fixTitle)}
      description={finding?.rule_name}
      closeLabel={fm(am.close)}
      size="lg"
      footer={
        journal && !draft ? (
          <>
            <Button variant="secondary" onClick={onClose}>
              {fm(am.cancel)}
            </Button>
            <Button
              variant="primary"
              disabled={busy || problem !== null}
              onClick={() => void create()}
            >
              {fm(am.createDraft)}
            </Button>
          </>
        ) : null
      }
    >
      <div className="flex flex-col gap-4" data-fix-drawer="">
        {fix === undefined ? <p className="text-sm text-fg-muted">{fm(am.loadingFix)}</p> : null}
        {fix === null ? <p className="text-sm text-fg">{fm(am.noFix)}</p> : null}
        {fix ? (
          <section className="flex flex-col gap-1" data-fix-kind={fix.kind}>
            <h3 className="text-sm font-semibold text-fg">{fm(am.fixWhy)}</h3>
            <p className="text-sm text-fg" data-fix-reasoning="">
              {fix.reasoning}
            </p>
          </section>
        ) : null}
        {fix && !journal ? (
          <div className="flex flex-col gap-2">
            {fix.recode && Object.keys(fix.recode.changes).length ? (
              <p className="text-sm text-fg-muted">
                {fm(am.recodeChanges, {
                  changes: Object.entries(fix.recode.changes)
                    .map(([field, value]) => `${field} → ${value}`)
                    .join(", "),
                })}
              </p>
            ) : null}
            <Link
              href={orgModuleUrl(org, "accounting/recode")}
              className="text-sm text-fg-accent-strong underline"
            >
              {fm(am.openRecode)}
            </Link>
          </div>
        ) : null}
        {journal ? (
          <>
            <div className="flex flex-wrap gap-3">
              <label className="flex flex-col gap-1 text-sm text-fg" htmlFor={`${ids}-date`}>
                {fm(am.fixDateLabel)}
                <Input
                  id={`${ids}-date`}
                  type="date"
                  value={date}
                  disabled={draft !== null}
                  onChange={(event) => setDate(event.target.value)}
                />
              </label>
              <label
                className="flex min-w-64 flex-1 flex-col gap-1 text-sm text-fg"
                htmlFor={`${ids}-narration`}
              >
                {fm(am.fixNarration)}
                <Input
                  id={`${ids}-narration`}
                  value={narration}
                  maxLength={1000}
                  disabled={draft !== null}
                  onChange={(event) => setNarration(event.target.value)}
                />
              </label>
            </div>
            <table className="w-full text-sm" data-fix-lines="">
              <caption className="pb-1 text-start text-sm font-semibold text-fg">
                {fm(am.fixLines)}
              </caption>
              <thead>
                <tr className="text-xs text-fg-muted">
                  <th scope="col" className="w-2/5 py-1 text-start">
                    {fm(am.account)}
                  </th>
                  <th scope="col" className="py-1 text-end">
                    {fm(am.debit)}
                  </th>
                  <th scope="col" className="py-1 text-end">
                    {fm(am.credit)}
                  </th>
                  <th scope="col" className="py-1 text-start">
                    {fm(am.description)}
                  </th>
                  <th scope="col" className="py-1">
                    <span className="sr-only">{fm(am.lineActions)}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {lines.map((line, index) => {
                  const n = index + 1;
                  return (
                    <tr key={line.key} className="border-t border-border align-top" data-line={n}>
                      <td className="py-2 pe-2">
                        <AccountPicker
                          aria-label={fm(am.accountOfLine, { line: n })}
                          accounts={pickerAccounts}
                          context="journal"
                          value={line.account || null}
                          disabled={draft !== null}
                          onChange={(account) => setLine(line.key, { account: account ?? "" })}
                          typeLabels={accountTypes}
                          emptyMessage={noAccounts}
                          placeholder={fm(am.chooseAccount)}
                        />
                      </td>
                      <td className="py-2 pe-2">
                        <Input
                          numeric
                          inputMode="decimal"
                          aria-label={fm(am.debitOfLine, { line: n })}
                          value={line.debit}
                          disabled={draft !== null}
                          onChange={(e) => setLine(line.key, { debit: e.target.value, credit: "" })}
                        />
                      </td>
                      <td className="py-2 pe-2">
                        <Input
                          numeric
                          inputMode="decimal"
                          aria-label={fm(am.creditOfLine, { line: n })}
                          value={line.credit}
                          disabled={draft !== null}
                          onChange={(e) => setLine(line.key, { credit: e.target.value, debit: "" })}
                        />
                      </td>
                      <td className="py-2 pe-2">
                        <Input
                          aria-label={fm(am.descriptionOfLine, { line: n })}
                          value={line.description}
                          maxLength={500}
                          disabled={draft !== null}
                          onChange={(e) => setLine(line.key, { description: e.target.value })}
                        />
                      </td>
                      <td className="py-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          aria-label={fm(am.removeLine, { line: n })}
                          disabled={draft !== null || lines.length <= 2}
                          onClick={() =>
                            setLines((current) => current.filter((l) => l.key !== line.key))
                          }
                        >
                          <CloseIcon />
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <Button
                size="sm"
                variant="secondary"
                disabled={draft !== null}
                onClick={() => setLines((current) => [...current, emptyGridLine()])}
              >
                {fm(am.addLine)}
              </Button>
              <p
                className="flex flex-wrap gap-3 text-sm text-fg"
                data-fix-totals={totals.balanced ? "balanced" : ""}
              >
                <span>
                  {fm(am.totals, { debit: money(totals.debit), credit: money(totals.credit) })}
                </span>
                <span className={totals.balanced ? "text-fg-success" : "text-fg-danger"}>
                  {totals.balanced
                    ? fm(am.balanced)
                    : fm(am.outOfBalance, {
                        amount: money(
                          totals.difference.startsWith("-")
                            ? totals.difference.slice(1)
                            : totals.difference,
                        ),
                      })}
                </span>
              </p>
            </div>
            {problem && !draft ? (
              <p className="text-sm text-fg-muted" data-fix-problem={problem}>
                {fm(am.problem, { problem })}
              </p>
            ) : null}
            {fix && fix.date ? (
              <p className="text-xs text-fg-muted">
                {fm(am.fixDate, { date: formatDate(fix.date, { locale }) })}
              </p>
            ) : null}
            {fix?.alternatives.map((alternative) => (
              <div
                key={alternative.reasoning}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-3"
                data-fix-alternative=""
              >
                <p className="max-w-xl text-sm text-fg-muted">
                  {fm(am.alternatives, { text: alternative.reasoning })}
                </p>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={draft !== null}
                  onClick={() => applyAlternative(alternative)}
                >
                  {fm(am.useAlternative)}
                </Button>
              </div>
            ))}
            <p className="text-xs text-fg-muted">{fm(am.draftNever)}</p>
          </>
        ) : null}
        {error ? (
          <p role="alert" className="text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
        {draft ? (
          <div className="flex flex-col gap-2" data-fix-draft={draft}>
            <p role="status" className="text-sm text-fg-success">
              {fm(am.draftCreated)}
            </p>
            <div className="flex flex-wrap gap-4">
              <Link
                href={`${journalsUrl}/${draft}`}
                className="text-sm text-fg-accent-strong underline"
              >
                {fm(am.openDraft)}
              </Link>
              <Link
                href={`${journalsUrl}?tab=draft`}
                className="text-sm text-fg-accent-strong underline"
              >
                {fm(am.openDraftTab)}
              </Link>
            </div>
          </div>
        ) : null}
      </div>
    </Drawer>
  );
}
