"use client";

/** The preview of a filing change (G-03a-T15): periods removed, added and shortened. */
import { formatDate, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";

import { useFormatMessage } from "@/i18n";

import type { FilingDiff } from "./api";
import { fmsg, kindLabels } from "./messages";

export function DiffList({ diff }: { diff: FilingDiff }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const date = (day: string) => formatDate(day, { locale });
  const empty = !diff.removed.length && !diff.added.length && !diff.changed.length;
  return (
    <div data-filing-diff="" className="flex flex-col gap-2 text-sm text-fg">
      <h3 className="font-semibold">{fm(fmsg.diffTitle)}</h3>
      {diff.warnings.map((warning) => (
        <p key={warning.code} role="status" data-warning={warning.code} className="text-fg-warning">
          {warning.message}
        </p>
      ))}
      {empty ? (
        <p>{fm(fmsg.noChange)}</p>
      ) : (
        <ul aria-label={fm(fmsg.diffTable)} className="flex flex-col gap-1">
          {diff.changed.map((change) => (
            <li key={`c-${change.after.id}`} data-diff="changed">
              {fm(fmsg.diffChangedRow, {
                start: date(change.before.start),
                before: date(change.before.end),
                after: date(change.after.end),
              })}
            </li>
          ))}
          {diff.removed.map((period) => (
            <li
              key={`r-${period.id}`}
              data-diff="removed"
              className="rounded-sm border border-dashed border-border px-1.5 text-fg-muted line-through"
            >
              {fm(fmsg.diffRemovedRow, { start: date(period.start), end: date(period.end) })}
            </li>
          ))}
          {diff.added.map((period) => (
            <li
              key={`a-${period.id}`}
              data-diff="added"
              className="rounded-sm border border-dashed border-fg px-1.5"
            >
              {fm(fmsg.diffAddedRow, {
                start: date(period.start),
                end: date(period.end),
                kind: fm(kindLabels[period.kind]),
              })}
            </li>
          ))}
        </ul>
      )}
      <p className="text-fg-muted" data-diff-summary="">
        {fm(fmsg.diffSummary, {
          removed: diff.removed.length,
          added: diff.added.length,
          changed: diff.changed.length,
        })}
      </p>
    </div>
  );
}
