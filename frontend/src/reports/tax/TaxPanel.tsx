"use client";

/**
 * Tax reports in the runner (G-05-T10): the **tie-out card** at the top of the tie-out report —
 * green "Ties to GL", or red with the difference and the journals that posted to a tax control
 * account without tax lines (each a link); the audit report's **flags as chips**; and every
 * document row's link (the drill-down to the document).
 */
import { Badge, formatMoney, type AppLocale } from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";

import { useFormatMessage } from "@/i18n";

import type { ReportBody, ReportRowData } from "../api";
import { tm } from "./messages";

interface TieJournal {
  journal: string;
  date: string;
  narration: string;
  amount: string;
  url: string;
}

const TIE_REPORT = "tax_tie_out";
const AUDIT_REPORT = "tax_audit";

function drillOf(row: ReportRowData): Record<string, unknown> {
  return (row.drill ?? {}) as Record<string, unknown>;
}

export function TieOutCard({ body }: { body: ReportBody }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const total = body.totals[0]?.values[2] ?? "0.00";
  const ties = Number(total) === 0 && body.rows.every((row) => Number(row.values[2] ?? 0) === 0);
  const off = body.rows.filter((row) => Number(row.values[2] ?? 0) !== 0);
  return (
    <section
      aria-labelledby="tie-out-title"
      data-tie-out={ties ? "ties" : "difference"}
      className={
        ties
          ? "rounded-lg border-2 border-border-success bg-surface-success-subtle p-4"
          : "rounded-lg border-2 border-border-danger bg-surface-danger-subtle p-4"
      }
    >
      <h2 id="tie-out-title" className="text-base font-semibold text-fg">
        {ties ? fm(tm.ties) : fm(tm.difference, { amount: formatMoney(total, { locale }) })}
      </h2>
      <p className="text-sm text-fg">{ties ? fm(tm.tiesBody) : fm(tm.differenceBody)}</p>
      {off.map((row) => {
        const journals = (drillOf(row).journals as TieJournal[] | undefined) ?? [];
        return (
          <div key={row.key} className="mt-3" data-tie-account={row.key}>
            <h3 className="text-sm font-semibold text-fg">
              {fm(tm.journalsTitle, { account: row.label })}
            </h3>
            <ul className="mt-1 flex flex-col gap-1 text-sm">
              {journals.map((journal) => (
                <li key={journal.journal + journal.amount}>
                  <Link href={journal.url} className="text-fg-accent underline">
                    {fm(tm.journalLine, {
                      journal: journal.journal,
                      date: journal.date,
                      narration: journal.narration,
                      amount: formatMoney(journal.amount, { locale }),
                    })}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </section>
  );
}

export function TaxRowsPanel({ body }: { body: ReportBody }) {
  const fm = useFormatMessage();
  const rows = body.rows.filter((row) => row.kind === "row");
  if (body.report === AUDIT_REPORT) {
    const flagged = rows.filter(
      (row) => ((drillOf(row).flags as string[] | undefined) ?? []).length > 0,
    );
    if (!flagged.length) return null;
    return (
      <section aria-labelledby="tax-flags" className="flex flex-col gap-2" data-tax-flags="">
        <h2 id="tax-flags" className="text-base font-semibold text-fg">
          {fm(tm.flagsTitle)}
        </h2>
        <ul className="flex flex-col gap-1 text-sm">
          {flagged.map((row) => {
            const drill = drillOf(row);
            return (
              <li
                key={row.key}
                className="flex flex-wrap items-center gap-2"
                data-flag-row={row.key}
              >
                <span>{row.label}</span>
                {((drill.flags as string[]) ?? []).map((flag) => (
                  <Badge key={flag} tone="warning" data-flag={flag}>
                    {fm(tm.flag, { flag })}
                  </Badge>
                ))}
                {typeof drill.url === "string" ? (
                  <Link href={drill.url} className="text-fg-accent underline">
                    {fm(tm.openDocument, { number: String(drill.number ?? "") })}
                  </Link>
                ) : null}
              </li>
            );
          })}
        </ul>
      </section>
    );
  }
  const linked = rows.filter((row) => typeof drillOf(row).url === "string");
  if (!linked.length) return null;
  return (
    <section aria-labelledby="tax-documents" className="flex flex-col gap-2" data-tax-documents="">
      <h2 id="tax-documents" className="text-base font-semibold text-fg">
        {fm(tm.documentsTitle)}
      </h2>
      <ul className="flex flex-col gap-1 text-sm">
        {linked.map((row) => {
          const drill = drillOf(row);
          return (
            <li key={row.key}>
              <Link href={String(drill.url)} className="text-fg-accent underline">
                {fm(tm.openDocument, { number: String(drill.number ?? row.label) })}
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** A tax figure's drill-down: the summary's figures open the detail for their code; a
 * document row opens the document. */
export function taxDrillHref(org: string, row: ReportRowData): string | null {
  const drill = drillOf(row);
  if (drill.report === "tax_detail") {
    const query = new URLSearchParams();
    for (const [key, name] of [
      ["from", "date_from"],
      ["to", "date_to"],
      ["code", "code"],
      ["component", "component"],
      ["side", "side"],
      ["basis", "basis"],
    ] as const) {
      const value = drill[key];
      if (typeof value === "string" && value) query.set(name, value);
    }
    return `/o/${org}/reports/tax-detail?${query.toString()}`;
  }
  return typeof drill.url === "string" ? drill.url : null;
}

export const TAX_PERIODS = ["current", "last_filed", ""] as const;
export { TIE_REPORT };
