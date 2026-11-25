"use client";

/**
 * Find & recode — the results (C-07-T11): the lines found, a page at a time, with a checkbox
 * per line, one for the page and — once the page is chosen — "Select all N lines" across every
 * page (the search's `keys`); a sticky summary "500 lines · 3 accounts · 12 excluded"; and the
 * **Excluded** tab listing the lines that can't be recoded, each with its reason.
 */
import { Button, Checkbox, formatDate, formatMoney, Tabs, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";

import { useFormatMessage } from "@/i18n";

import type { ExcludedLine, FoundLine, SearchResult } from "./api";
import { rm } from "./messages";
import { keyOf, setMany, toggle } from "./selection";

export interface RecodeResultsProps {
  result: SearchResult;
  selected: Set<string>;
  onSelectedChange: (selected: Set<string>) => void;
  onPage: (page: number) => void;
}

function tracking(value: Record<string, string>) {
  return Object.entries(value)
    .map(([k, v]) => `${k}: ${v}`)
    .join("; ");
}

export function RecodeResults({ result, selected, onSelectedChange, onPage }: RecodeResultsProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const pages = Math.max(1, Math.ceil(result.count / result.page_size));
  const pageKeys = result.lines.map(keyOf);
  const pageChosen = pageKeys.length > 0 && pageKeys.every((key) => selected.has(key));
  const somePage = pageKeys.some((key) => selected.has(key));
  const allKeys = result.keys.map(keyOf);
  const allChosen = allKeys.length > 0 && allKeys.every((key) => selected.has(key));
  const money = (value: string) => (Number(value) ? formatMoney(value, { locale }) : "");
  const day = (value: string) => formatDate(value, { locale });

  const heads = (last: string) => (
    <>
      <th scope="col" className="p-1">
        {fm(rm.colJournal)}
      </th>
      <th scope="col" className="p-1">
        {fm(rm.colDate)}
      </th>
      <th scope="col" className="p-1">
        {fm(rm.colAccount)}
      </th>
      <th scope="col" className="p-1">
        {fm(rm.colDescription)}
      </th>
      <th scope="col" className="p-1 text-end">
        {fm(rm.colDebit)}
      </th>
      <th scope="col" className="p-1 text-end">
        {fm(rm.colCredit)}
      </th>
      <th scope="col" className="p-1">
        {fm(rm.colTax)}
      </th>
      <th scope="col" className="p-1">
        {fm(rm.colContact)}
      </th>
      <th scope="col" className="p-1">
        {last}
      </th>
    </>
  );

  const cells = (line: FoundLine | ExcludedLine) => (
    <>
      <td className="p-1 font-medium whitespace-nowrap">
        {fm(rm.journalLine, { number: line.number, line: line.line_no })}
      </td>
      <td className="p-1 whitespace-nowrap">{day(line.date)}</td>
      <td className="p-1">{line.account.label}</td>
      <td className="p-1">{line.description || line.narration}</td>
      <td className="p-1 text-end tabular-nums">{money(line.debit)}</td>
      <td className="p-1 text-end tabular-nums">{money(line.credit)}</td>
      <td className="p-1">{line.tax_code}</td>
      <td className="p-1">{line.contact?.label ?? ""}</td>
    </>
  );

  const found = (
    <div className="flex flex-col gap-2" data-recode-results="">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span data-selected-count="">{fm(rm.selected, { selected: selected.size })}</span>
        {pageChosen && !allChosen && result.count > result.lines.length ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => onSelectedChange(setMany(selected, allKeys, true))}
          >
            {fm(rm.selectAll, { count: result.count })}
          </Button>
        ) : null}
        {selected.size ? (
          <Button variant="ghost" size="sm" onClick={() => onSelectedChange(new Set())}>
            {fm(rm.clearSelection)}
          </Button>
        ) : null}
      </div>
      {result.lines.length === 0 ? (
        <p className="text-sm text-fg-muted">{fm(rm.noLines)}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-fg-muted">
                <th scope="col" className="w-10 p-1">
                  <Checkbox
                    aria-label={fm(rm.selectPage)}
                    checked={pageChosen ? true : somePage ? "indeterminate" : false}
                    onCheckedChange={(on) =>
                      onSelectedChange(setMany(selected, pageKeys, on === true))
                    }
                  />
                </th>
                {heads(fm(rm.colTracking))}
              </tr>
            </thead>
            <tbody>
              {result.lines.map((line) => {
                const key = keyOf(line);
                return (
                  <tr key={key} className="border-t border-border" data-line={key}>
                    <td className="p-1">
                      <Checkbox
                        aria-label={fm(rm.selectLine, { number: line.number, line: line.line_no })}
                        checked={selected.has(key)}
                        onCheckedChange={() => onSelectedChange(toggle(selected, key))}
                      />
                    </td>
                    {cells(line)}
                    <td className="p-1">{tracking(line.tracking)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {pages > 1 ? (
        <nav className="flex items-center gap-2 text-sm" aria-label={fm(rm.results)}>
          <Button
            variant="secondary"
            size="sm"
            disabled={result.page <= 1}
            onClick={() => onPage(result.page - 1)}
          >
            {fm(rm.previous)}
          </Button>
          <span>{fm(rm.page, { page: result.page, pages })}</span>
          <Button
            variant="secondary"
            size="sm"
            disabled={result.page >= pages}
            onClick={() => onPage(result.page + 1)}
          >
            {fm(rm.next)}
          </Button>
        </nav>
      ) : null}
    </div>
  );

  const excluded = (
    <div className="overflow-x-auto" data-recode-excluded="">
      {result.excluded.length === 0 ? (
        <p className="text-sm text-fg-muted">{fm(rm.noExcluded)}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-fg-muted">{heads(fm(rm.colReason))}</tr>
          </thead>
          <tbody>
            {result.excluded.map((line) => (
              <tr
                key={keyOf(line)}
                className="border-t border-border"
                data-excluded={line.reason.code}
              >
                {cells(line)}
                <td className="p-1 text-fg-warning">{line.reason.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );

  return (
    <section className="flex flex-col gap-2">
      <p
        className="sticky top-0 z-10 bg-surface py-1 text-sm font-medium text-fg"
        data-recode-summary=""
      >
        {fm(rm.summary, {
          lines: result.count,
          accounts: result.accounts,
          excluded: result.excluded_count,
        })}
      </p>
      <Tabs
        label={fm(rm.results)}
        items={[
          { value: "found", label: fm(rm.results), count: result.count, content: found },
          {
            value: "excluded",
            label: fm(rm.excludedTab),
            count: result.excluded_count,
            content: excluded,
          },
        ]}
        defaultValue="found"
      />
    </section>
  );
}
