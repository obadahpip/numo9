"use client";

import {
  Badge,
  ErrorState,
  formatDate,
  formatDateTime,
  formatMoney,
  LoadingRegion,
  SkeletonTable,
  type BadgeTone,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";
import type { AppLocale } from "@/i18n/locales";

import { getJournal, type Book, type Journal, type JournalStatus } from "./api";

const m = defineMessages({
  title: {
    id: "journals.viewer.title",
    defaultMessage: "Journal {number}",
    description: "Page heading of a posted journal entry, e.g. Journal JE-000042",
  },
  draftTitle: {
    id: "journals.viewer.draftTitle",
    defaultMessage: "Draft journal",
    description: "Page heading of a journal entry that has no number yet",
  },
  readOnly: {
    id: "journals.viewer.readOnly",
    defaultMessage:
      "Posted journals can't be changed. To correct one, reverse it and post a new journal.",
    description: "Note under the heading of the read-only journal viewer",
  },
  date: { id: "journals.viewer.date", defaultMessage: "Date", description: "Field label" },
  type: { id: "journals.viewer.type", defaultMessage: "Type", description: "Field label" },
  status: { id: "journals.viewer.status", defaultMessage: "Status", description: "Field label" },
  narration: {
    id: "journals.viewer.narration",
    defaultMessage: "Narration",
    description: "Field label: what the journal is for",
  },
  source: {
    id: "journals.viewer.source",
    defaultMessage: "Source",
    description: "Field label: the document that posted the journal",
  },
  manual: {
    id: "journals.viewer.manual",
    defaultMessage: "Entered directly",
    description: "Source value when no document posted the journal",
  },
  books: {
    id: "journals.viewer.books",
    defaultMessage: "Books",
    description: "Field label: which books (accounting, tax) the journal is in",
  },
  postedBy: {
    id: "journals.viewer.postedBy",
    defaultMessage: "Posted",
    description: "Field label: who posted the journal and when",
  },
  postedByValue: {
    id: "journals.viewer.postedByValue",
    defaultMessage: "{when} by {person}",
    description: "Posted field value, e.g. 15 Apr 2026, 3:12 p.m. by Olivia Tremblay",
  },
  system: {
    id: "journals.viewer.system",
    defaultMessage: "the system",
    description: "Who posted a journal posted by a background process",
  },
  reverses: {
    id: "journals.viewer.reverses",
    defaultMessage: "This journal reverses {link}.",
    description: "Link to the journal this one reverses",
  },
  reversedBy: {
    id: "journals.viewer.reversedBy",
    defaultMessage: "Reversed by {link}.",
    description: "Link to the journal that reversed this one",
  },
  lines: {
    id: "journals.viewer.lines",
    defaultMessage: "Lines",
    description: "Heading of the journal lines table",
  },
  colLine: {
    id: "journals.viewer.colLine",
    defaultMessage: "#",
    description: "Column: line number",
  },
  colAccount: {
    id: "journals.viewer.colAccount",
    defaultMessage: "Account",
    description: "Column",
  },
  colDescription: {
    id: "journals.viewer.colDescription",
    defaultMessage: "Description",
    description: "Column",
  },
  colContact: {
    id: "journals.viewer.colContact",
    defaultMessage: "Contact",
    description: "Column",
  },
  colTax: { id: "journals.viewer.colTax", defaultMessage: "Tax code", description: "Column" },
  colBook: { id: "journals.viewer.colBook", defaultMessage: "Book", description: "Column" },
  colDebit: { id: "journals.viewer.colDebit", defaultMessage: "Debit", description: "Column" },
  colCredit: { id: "journals.viewer.colCredit", defaultMessage: "Credit", description: "Column" },
  totalIn: {
    id: "journals.viewer.totalIn",
    defaultMessage: "Total, {book}",
    description: "Totals row of one book, e.g. Total, tax book",
  },
  activity: {
    id: "journals.viewer.activity",
    defaultMessage: "Activity",
    description: "Heading of the journal's audit trail",
  },
  loading: {
    id: "journals.viewer.loading",
    defaultMessage: "Loading the journal…",
    description: "Screen-reader text while loading",
  },
  loadFailed: {
    id: "journals.viewer.loadFailed",
    defaultMessage: "The journal didn't load",
    description: "Error title",
  },
  loadFailedBody: {
    id: "journals.viewer.loadFailedBody",
    defaultMessage: "Verify your connection and try again.",
    description: "Error body",
  },
  notFound: {
    id: "journals.viewer.notFound",
    defaultMessage: "There's no journal with this link in this organisation",
    description: "Error title when the journal doesn't exist",
  },
  notFoundBody: {
    id: "journals.viewer.notFoundBody",
    defaultMessage: "It may belong to another organisation. Verify the link.",
    description: "Error body when the journal doesn't exist",
  },
  retry: { id: "journals.viewer.retry", defaultMessage: "Try again", description: "Button" },
  none: { id: "journals.viewer.none", defaultMessage: "—", description: "Empty field value" },
  sourceValue: {
    id: "journals.viewer.sourceValue",
    defaultMessage: "{type} · {id}",
    description: "Source document: its type and id",
  },
  activityLine: {
    id: "journals.viewer.activityLine",
    defaultMessage: "{action} · {when} · {person}",
    description:
      "One line of the journal's audit trail, e.g. Posted · 15 Apr 2026, 3:12 p.m. · Olivia",
  },
  bookBadge: {
    id: "journals.viewer.bookBadge",
    defaultMessage:
      "{book, select, both {Both books} accounting {Accounting book} tax {Tax book} other {{book}}}",
    description: "Book badge on a journal or a line",
  },
  bookName: {
    id: "journals.viewer.bookName",
    defaultMessage: "{book, select, accounting {accounting book} tax {tax book} other {{book}}}",
    description: "Book name inside a sentence (lower case)",
  },
  statusName: {
    id: "journals.viewer.statusName",
    defaultMessage:
      "{status, select, draft {Draft} awaiting_approval {Awaiting approval} posted {Posted} reversed {Reversed} other {{status}}}",
    description: "Journal status badge",
  },
  typeName: {
    id: "journals.viewer.typeName",
    defaultMessage:
      "{type, select, manual {Manual journal} sales {Sales} purchase {Purchases} payment {Payment} payroll {Payroll} opening {Opening balance} adjustment {Adjustment} reversal {Reversal} other {{type}}}",
    description: "Journal type",
  },
  action: {
    id: "journals.viewer.action",
    defaultMessage:
      "{action, select, ledger_journalentry_posted {Posted} ledger_journalentry_reversed {Reversed} ledger_journalentry_created {Created} ledger_journalentry_updated {Edited} other {{action}}}",
    description: "Audit trail action of a journal",
  },
});

const BOOK_TONES: Record<Book, BadgeTone> = { both: "neutral", accounting: "info", tax: "warning" };
const STATUS_TONES: Record<JournalStatus, BadgeTone> = {
  draft: "neutral",
  awaiting_approval: "warning",
  posted: "success",
  reversed: "danger",
};

/** Placeholder for a link inside a translated sentence (split around it). */
const MARK = "\u2063LINK\u2063";

function withLink(text: string, link: ReactNode): ReactNode {
  const [before, after = ""] = text.split(MARK);
  return (
    <>
      {before}
      {link}
      {after}
    </>
  );
}

type State =
  | { kind: "loading" }
  | { kind: "failed" }
  | { kind: "missing" }
  | { kind: "ready"; journal: Journal };

/** Read-only journal viewer (C-02-T16): header, book badges, lines, totals per book, reversal links. */
export function JournalViewer({ org, id }: Readonly<{ org: string; id: string }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    const answer = await getJournal(org, id);
    if (answer.status === 200) setState({ kind: "ready", journal: answer.body });
    else if (answer.status === 404) setState({ kind: "missing" });
    else setState({ kind: "failed" });
  }, [org, id]);
  useEffect(() => {
    void load();
  }, [load]);

  if (state.kind === "loading")
    return (
      <LoadingRegion label={fm(m.loading)}>
        <SkeletonTable rows={4} columns={8} />
      </LoadingRegion>
    );
  if (state.kind === "missing")
    return (
      <ErrorState
        title={fm(m.notFound)}
        body={fm(m.notFoundBody)}
        retryLabel={fm(m.retry)}
        onRetry={() => void load()}
      />
    );
  if (state.kind === "failed")
    return (
      <ErrorState
        title={fm(m.loadFailed)}
        body={fm(m.loadFailedBody)}
        retryLabel={fm(m.retry)}
        onRetry={() => void load()}
      />
    );

  const journal = state.journal;
  const money = (amount: string) => formatMoney(amount, { locale });
  const journalLink = (link: { id: string; number: string }) => (
    <Link
      href={`/o/${org}/accounting/journals/${link.id}`}
      prefetch={false}
      className="font-medium text-fg-accent underline"
    >
      {link.number}
    </Link>
  );
  const bookBadge = (book: Book) => (
    <Badge tone={BOOK_TONES[book]} data-book={book}>
      {fm(m.bookBadge, { book })}
    </Badge>
  );
  const scopeBooks: Book[] =
    journal.book_scope === "both" ? ["accounting", "tax"] : [journal.book_scope];

  return (
    <article className="flex flex-col gap-6" aria-labelledby="journal-title">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 id="journal-title" className="text-2xl font-semibold">
            {journal.number ? fm(m.title, { number: journal.number }) : fm(m.draftTitle)}
          </h1>
          <Badge tone={STATUS_TONES[journal.status]} dot>
            {fm(m.statusName, { status: journal.status })}
          </Badge>
          {scopeBooks.map((book) => (
            <span key={book}>{bookBadge(book)}</span>
          ))}
        </div>
        <p className="text-fg-muted">{fm(m.readOnly)}</p>
        {journal.reversal_of ? (
          <p data-reverses>
            {withLink(fm(m.reverses, { link: MARK }), journalLink(journal.reversal_of))}
          </p>
        ) : null}
        {journal.reversed_by ? (
          <p data-reversed-by>
            {withLink(fm(m.reversedBy, { link: MARK }), journalLink(journal.reversed_by))}
          </p>
        ) : null}
      </header>

      <dl className="grid max-w-3xl grid-cols-[max-content_1fr] gap-x-6 gap-y-2">
        <dt className="text-fg-muted">{fm(m.date)}</dt>
        <dd>{formatDate(journal.date, { locale })}</dd>
        <dt className="text-fg-muted">{fm(m.type)}</dt>
        <dd>{fm(m.typeName, { type: journal.type })}</dd>
        <dt className="text-fg-muted">{fm(m.narration)}</dt>
        <dd>{journal.narration || fm(m.none)}</dd>
        <dt className="text-fg-muted">{fm(m.source)}</dt>
        <dd>
          {journal.source
            ? fm(m.sourceValue, { type: journal.source.type, id: journal.source.id })
            : fm(m.manual)}
        </dd>
        <dt className="text-fg-muted">{fm(m.postedBy)}</dt>
        <dd>
          {journal.posted_at
            ? fm(m.postedByValue, {
                when: formatDateTime(journal.posted_at, { locale }),
                person: journal.posted_by?.name ?? fm(m.system),
              })
            : fm(m.none)}
        </dd>
      </dl>

      <section aria-labelledby="journal-lines" className="flex flex-col gap-2">
        <h2 id="journal-lines" className="text-lg font-semibold">
          {fm(m.lines)}
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-start text-fg-muted">
                <th scope="col" className="py-2 pe-3 text-start">
                  {fm(m.colLine)}
                </th>
                <th scope="col" className="py-2 pe-3 text-start">
                  {fm(m.colAccount)}
                </th>
                <th scope="col" className="py-2 pe-3 text-start">
                  {fm(m.colDescription)}
                </th>
                <th scope="col" className="py-2 pe-3 text-start">
                  {fm(m.colContact)}
                </th>
                <th scope="col" className="py-2 pe-3 text-start">
                  {fm(m.colTax)}
                </th>
                <th scope="col" className="py-2 pe-3 text-start">
                  {fm(m.colBook)}
                </th>
                <th scope="col" className="py-2 pe-3 text-end">
                  {fm(m.colDebit)}
                </th>
                <th scope="col" className="py-2 text-end">
                  {fm(m.colCredit)}
                </th>
              </tr>
            </thead>
            <tbody>
              {journal.lines.map((line) => (
                <tr key={line.line} className="border-b border-border" data-line={line.line}>
                  <td className="py-2 pe-3">{line.line}</td>
                  <td className="py-2 pe-3">
                    <span className="font-mono">{line.account.code}</span> {line.account.name}
                  </td>
                  <td className="py-2 pe-3">{line.description}</td>
                  <td className="py-2 pe-3">{line.contact?.name ?? ""}</td>
                  <td className="py-2 pe-3">{line.tax_code}</td>
                  <td className="py-2 pe-3">{bookBadge(line.book)}</td>
                  <td className="py-2 pe-3 text-end tabular-nums">
                    {Number(line.debit) ? money(line.debit) : ""}
                  </td>
                  <td className="py-2 text-end tabular-nums">
                    {Number(line.credit) ? money(line.credit) : ""}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              {(["accounting", "tax"] as const).map((book) => {
                const totals = journal.books[book];
                if (!totals) return null;
                return (
                  <tr key={book} className="font-semibold" data-total={book}>
                    <th scope="row" colSpan={6} className="py-2 pe-3 text-end">
                      {fm(m.totalIn, { book: fm(m.bookName, { book }) })}
                    </th>
                    <td className="py-2 pe-3 text-end tabular-nums">{money(totals.debit)}</td>
                    <td className="py-2 text-end tabular-nums">{money(totals.credit)}</td>
                  </tr>
                );
              })}
            </tfoot>
          </table>
        </div>
      </section>

      {journal.audit.length ? (
        <section aria-labelledby="journal-activity" className="flex flex-col gap-2">
          <h2 id="journal-activity" className="text-lg font-semibold">
            {fm(m.activity)}
          </h2>
          <ul className="flex flex-col gap-1 text-sm">
            {journal.audit.map((event) => (
              <li key={`${event.action}-${event.at}`}>
                {fm(m.activityLine, {
                  action: fm(m.action, { action: event.action.replaceAll(".", "_") }),
                  when: formatDateTime(event.at, { locale }),
                  person: event.by,
                })}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}
