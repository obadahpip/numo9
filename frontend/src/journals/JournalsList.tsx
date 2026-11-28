"use client";

/**
 * Journals list (K-09-T22 seam for the Phase 1 journals list), `/o/:org/accounting/journals`:
 * tabs All / Draft / Awaiting approval / Posted / Reversed over `GET journals?status=`, a search
 * over narration and number, newest first, 50 at a time. A row opens the journal. `?tab=draft`
 * opens a tab directly — the Assurance fix drawer links there after it creates a draft.
 */
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  formatDate,
  formatMoney,
  INPUT_BASE,
  Tabs,
  type AppLocale,
  type BadgeTone,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

import {
  isJournalTab,
  JOURNAL_TABS,
  listJournals,
  type JournalStatus,
  type JournalSummary,
  type JournalTab,
} from "./api";
import { jl } from "./listMessages";

const TONES: Record<JournalStatus, BadgeTone> = {
  draft: "neutral",
  awaiting_approval: "warning",
  posted: "success",
  reversed: "danger",
};

type Loaded = { rows: JournalSummary[]; count: number; next: number | null };

export function JournalsList({
  org,
  initialTab = "all",
}: {
  org: string;
  initialTab?: JournalTab;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const searchId = useId();
  const [tab, setTab] = useState<JournalTab>(initialTab);
  const [text, setText] = useState("");
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    const timer = setTimeout(
      () => {
        void listJournals(org, tab, { q: text })
          .catch(() => null)
          .then((answer) => {
            if (cancelled) return;
            if (answer?.status === 200 && Array.isArray(answer.body?.results)) {
              setLoaded({
                rows: answer.body.results,
                count: answer.body.count,
                next: answer.body.next_offset,
              });
            } else setFailed(true);
          });
      },
      text ? 250 : 0,
    );
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [org, tab, text, attempt]);

  const more = async () => {
    if (!loaded?.next) return;
    const answer = await listJournals(org, tab, { q: text, offset: loaded.next }).catch(() => null);
    if (answer?.status === 200)
      setLoaded({
        rows: [...loaded.rows, ...answer.body.results],
        count: answer.body.count,
        next: answer.body.next_offset,
      });
    else setFailed(true);
  };

  const href = (row: JournalSummary) => `${orgModuleUrl(org, "accounting/journals")}/${row.id}`;

  const panel = (
    <div className="flex flex-col gap-3 pt-3">
      {failed ? (
        <ErrorState
          title={fm(jl.failed)}
          retryLabel={fm(jl.retry)}
          onRetry={() => setAttempt((n) => n + 1)}
        />
      ) : null}
      {loaded && !failed && loaded.rows.length === 0 ? (
        <EmptyState title={fm(jl.empty)} body={fm(jl.emptyBody)} compact />
      ) : null}
      {loaded && loaded.rows.length > 0 ? (
        <>
          <p className="text-sm text-fg-muted">{fm(jl.count, { count: loaded.count })}</p>
          <table className="w-full text-sm" data-journals-table={tab}>
            <thead>
              <tr className="text-xs text-fg-muted">
                <th scope="col" className="py-1 text-start">
                  {fm(jl.number)}
                </th>
                <th scope="col" className="py-1 text-start">
                  {fm(jl.date)}
                </th>
                <th scope="col" className="py-1 text-start">
                  {fm(jl.narration)}
                </th>
                <th scope="col" className="py-1 text-start">
                  {fm(jl.type)}
                </th>
                <th scope="col" className="py-1 text-start">
                  {fm(jl.status)}
                </th>
                <th scope="col" className="py-1 text-end">
                  {fm(jl.total)}
                </th>
              </tr>
            </thead>
            <tbody>
              {loaded.rows.map((row) => (
                <tr key={row.id} className="border-t border-border" data-journal-row={row.id}>
                  <td className="py-2 pe-2">
                    <Link href={href(row)} className="font-semibold text-fg underline">
                      {row.number || fm(jl.draftNumber)}
                    </Link>
                  </td>
                  <td className="py-2 pe-2 whitespace-nowrap">
                    {formatDate(row.date, { locale })}
                  </td>
                  <td className="py-2 pe-2">{row.narration}</td>
                  <td className="py-2 pe-2">{row.journal_type_label}</td>
                  <td className="py-2 pe-2">
                    <Badge tone={TONES[row.status]} dot>
                      {fm(jl.statusName, { status: row.status })}
                    </Badge>
                  </td>
                  <td className="py-2 text-end tabular-nums">
                    {formatMoney(row.total, { locale })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {loaded.next !== null ? (
            <div>
              <Button size="sm" variant="secondary" onClick={() => void more()}>
                {fm(jl.more)}
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );

  return (
    <div className="flex flex-col gap-4" data-journals-list="">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <h1 className="text-2xl font-bold text-fg">{fm(jl.title)}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={orgModuleUrl(org, "accounting/journals/recurring")}
            className="inline-flex min-h-touch-target items-center px-2 text-sm font-semibold text-fg underline"
          >
            {fm(jl.recurring)}
          </Link>
          <Link
            href={orgModuleUrl(org, "accounting/journals/new")}
            className="inline-flex min-h-touch-target items-center rounded-md bg-surface-accent px-4 text-sm font-semibold text-fg-on-accent hover:bg-surface-accent-hover"
          >
            {fm(jl.newJournal)}
          </Link>
        </div>
      </header>
      <label className="flex max-w-sm flex-col gap-1 text-sm text-fg" htmlFor={searchId}>
        {fm(jl.search)}
        <input
          id={searchId}
          type="search"
          className={`${INPUT_BASE} border-border`}
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      </label>
      <Tabs
        label={fm(jl.tabs)}
        value={tab}
        onValueChange={(value) => {
          if (!isJournalTab(value)) return;
          setTab(value);
          setLoaded(null);
          const url = new URL(window.location.href);
          if (value === "all") url.searchParams.delete("tab");
          else url.searchParams.set("tab", value);
          window.history.replaceState(null, "", url.toString());
        }}
        items={JOURNAL_TABS.map((value) => ({
          value,
          label: fm(jl.tab, { tab: value }),
          content: value === tab ? panel : null,
        }))}
      />
    </div>
  );
}
