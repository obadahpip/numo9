"use client";

/**
 * Quotes list (D-02-T14), `/o/:org/sales/quotes`: tabs All · Draft · Sent · Accepted · Declined ·
 * Expired · Invoiced with their counts — the server's `tabs`, summed from its counts per
 * `QuoteStatus` (`quotes.status_counts`, the overview card's source too: one enum, one count,
 * gap-05). Sent shows sent and viewed quotes (the status badge tells which). Search by number,
 * title, reference, customer or amount; 50 a page, newest first; a row opens the quote.
 */
import {
  Badge,
  Button,
  ErrorState,
  Input,
  Skeleton,
  Tabs,
  formatMoney,
  type AppLocale,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import Link from "next/link";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { QUOTE_TABS, quotesApi, type QuoteList, type QuoteTab } from "./api";
import { listMessages as lm, quoteStatusLabels, tabLabels } from "./messages";

export function QuotesList({ org, initialTab = "all" }: { org: string; initialTab?: QuoteTab }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [tab, setTab] = useState<QuoteTab>(initialTab);
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [list, setList] = useState<QuoteList | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    const query: Record<string, string> = { tab, page: String(page) };
    if (search) query.q = search;
    void quotesApi.list(org, query).then((result) => {
      if (!live) return;
      if (result.status === 200 && result.body.tabs) {
        setList(result.body);
        setFailed(false);
      } else setFailed(true);
    });
    return () => {
      live = false;
    };
  }, [org, tab, page, search]);

  if (failed && !list) {
    return (
      <ErrorState
        title={fm(lm.loadFailed)}
        retryLabel={fm(lm.retry)}
        onRetry={() => window.location.reload()}
      />
    );
  }

  const table = !list ? (
    <Skeleton className="h-64" />
  ) : list.results.length === 0 ? (
    <p className="p-4 text-sm text-fg-muted">{search ? fm(lm.noMatches) : fm(lm.empty)}</p>
  ) : (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-quotes-table="">
        <thead>
          <tr className="border-b border-border text-start text-fg-muted">
            <th scope="col" className="p-2 text-start">
              {fm(lm.number)}
            </th>
            <th scope="col" className="p-2 text-start">
              {fm(lm.customer)}
            </th>
            <th scope="col" className="p-2 text-start">
              {fm(lm.title)}
            </th>
            <th scope="col" className="p-2 text-start">
              {fm(lm.date)}
            </th>
            <th scope="col" className="p-2 text-start">
              {fm(lm.expiry)}
            </th>
            <th scope="col" className="p-2 text-start">
              {fm(lm.status)}
            </th>
            <th scope="col" className="p-2 text-end">
              {fm(lm.total)}
            </th>
          </tr>
        </thead>
        <tbody>
          {list.results.map((quote) => (
            <tr key={quote.id} className="border-b border-border" data-quote-row={quote.status}>
              <td className="p-2">
                <Link href={quote.url} className="font-medium underline">
                  {quote.number}
                </Link>
              </td>
              <td className="p-2">{quote.customer.name}</td>
              <td className="p-2">{quote.title}</td>
              <td className="p-2 tabular-nums">{quote.date}</td>
              <td className="p-2 tabular-nums">{quote.expiry_date}</td>
              <td className="p-2">
                <Badge tone="neutral">{fm(quoteStatusLabels[quote.status])}</Badge>
              </td>
              <td className="p-2 text-end tabular-nums">{formatMoney(quote.total, { locale })}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {list.pages > 1 ? (
        <div className="flex items-center gap-3 p-2 text-sm">
          <Button size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
            {fm(lm.previous)}
          </Button>
          <span>{fm(lm.page, { page: list.page, pages: list.pages })}</span>
          <Button size="sm" disabled={page >= list.pages} onClick={() => setPage(page + 1)}>
            {fm(lm.next)}
          </Button>
        </div>
      ) : null}
    </div>
  );

  return (
    <div className="flex max-w-6xl flex-col gap-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-fg">{fm(lm.heading)}</h1>
        <Button asChild variant="primary">
          <Link href={`/o/${org}/sales/quotes/new`}>{fm(lm.newQuote)}</Link>
        </Button>
      </header>
      <form
        role="search"
        aria-label={fm(lm.search)}
        onSubmit={(event) => {
          event.preventDefault();
          setPage(1);
          setSearch(text.trim());
        }}
        className="flex flex-wrap items-end gap-2"
      >
        <label htmlFor={`${ids}-q`} className="sr-only">
          {fm(lm.search)}
        </label>
        <Input
          id={`${ids}-q`}
          type="search"
          value={text}
          placeholder={fm(lm.searchHint)}
          onChange={(e) => setText(e.target.value)}
          className="w-72"
        />
        <Button type="submit">{fm(lm.searchButton)}</Button>
      </form>
      <Tabs
        label={fm(lm.tabs)}
        value={tab}
        onValueChange={(value) => {
          setTab(value as QuoteTab);
          setPage(1);
        }}
        items={QUOTE_TABS.map((value) => ({
          value,
          label: fm(tabLabels[value]),
          count: list?.tabs[value],
          content: value === tab ? table : null,
        }))}
      />
    </div>
  );
}
