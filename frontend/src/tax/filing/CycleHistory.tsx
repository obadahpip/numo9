"use client";

/**
 * Filing frequency history (G-03a-T21): every frequency the registration has had, newest first
 * — from which date, who recorded it and when, and the CRA / Revenu Québec approval reference
 * (with its date and the note). The one in force today is marked.
 */
import { Badge, formatDate, formatDateTime, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";

import { useFormatMessage } from "@/i18n";

import type { FilingCycle } from "./api";
import { fmsg, frequencyLabels } from "./messages";

const TIME_ZONE = "America/Toronto";
const NONE = "—";

export function CycleHistory({ cycles, today }: { cycles: FilingCycle[]; today: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ordered = [...cycles].sort((a, b) => b.effective_from.localeCompare(a.effective_from));
  const current = ordered.find((c) => c.effective_from <= today) ?? ordered[ordered.length - 1];
  return (
    <section data-cycle-history="" className="flex flex-col gap-2">
      <h2 className="text-base font-semibold text-fg">{fm(fmsg.historyTitle)}</h2>
      {ordered.length === 0 ? (
        <p className="text-sm text-fg-muted">{fm(fmsg.historyNone)}</p>
      ) : (
        <table aria-label={fm(fmsg.historyTable)} className="w-full text-left text-sm text-fg">
          <thead className="text-xs text-fg-muted">
            <tr>
              <th scope="col" className="py-1 pr-3 font-medium">
                {fm(fmsg.historyFrom)}
              </th>
              <th scope="col" className="py-1 pr-3 font-medium">
                {fm(fmsg.historyFrequency)}
              </th>
              <th scope="col" className="py-1 pr-3 font-medium">
                {fm(fmsg.historyApproval)}
              </th>
              <th scope="col" className="py-1 pr-3 font-medium">
                {fm(fmsg.historyBy)}
              </th>
              <th scope="col" className="py-1 font-medium">
                {fm(fmsg.historyWhen)}
              </th>
            </tr>
          </thead>
          <tbody>
            {ordered.map((cycle) => (
              <tr
                key={cycle.id}
                data-cycle={cycle.effective_from}
                className="border-t border-border"
              >
                <td className="py-1.5 pr-3 whitespace-nowrap">
                  {formatDate(cycle.effective_from, { locale })}
                </td>
                <td className="py-1.5 pr-3">
                  <span className="flex flex-wrap items-center gap-2">
                    {fm(frequencyLabels[cycle.frequency])}
                    {cycle === current ? (
                      <Badge tone="info">{fm(fmsg.historyCurrent)}</Badge>
                    ) : null}
                  </span>
                </td>
                <td className="py-1.5 pr-3">
                  {cycle.approval_ref
                    ? cycle.approval_date
                      ? fm(fmsg.historyApprovalOn, {
                          ref: cycle.approval_ref,
                          date: formatDate(cycle.approval_date, { locale }),
                        })
                      : cycle.approval_ref
                    : NONE}
                  {cycle.note ? <span className="block text-fg-muted">{cycle.note}</span> : null}
                </td>
                <td className="py-1.5 pr-3">{cycle.created_by || fm(fmsg.historySystem)}</td>
                <td className="py-1.5 whitespace-nowrap">
                  {formatDateTime(cycle.created_at, { locale, timeZone: TIME_ZONE })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
