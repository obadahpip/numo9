"use client";

/**
 * Tax codes (G-01-T12, wireframe 43): Sales / Purchases tabs with counts, a type badge per code
 * (Taxable, Zero-rated, Exempt, Out of scope — never confused, gap-08), the components and their
 * rates, an effective timeline per version, how many posted lines used the code, and a "Show
 * expired rates" toggle — off by default, so ended rates (MB RST 8 %, NS HST 15 %) stay hidden.
 * A row opens the editor (G-01-T13).
 */
import {
  Badge,
  EmptyState,
  ErrorState,
  Input,
  SkeletonText,
  Switch,
  Tabs,
  formatDate,
  type AppLocale,
  type BadgeTone,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useId, useMemo, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { taxApi, type TaxCode, type TaxCodeType, type TaxSide } from "./api";
import { m, typeLabels } from "./messages";
import { taxSettingsUrl } from "./settings/links";

const TIME_ZONE = "America/Toronto";
const TONES: Record<TaxCodeType, BadgeTone> = {
  taxable: "info",
  zero_rated: "success",
  exempt: "warning",
  out_of_scope: "neutral",
};
/** Timeline scale: 1991 (GST) to 2032. */
const START = Date.UTC(1991, 0, 1);
const END = Date.UTC(2032, 0, 1);

function position(day: string | null, fallback: number): number {
  const at = day ? Date.parse(`${day}T00:00:00Z`) : fallback;
  return Math.min(100, Math.max(0, ((at - START) / (END - START)) * 100));
}

export interface TaxCodesScreenProps {
  org: string;
  /** Whether the person may add codes (tax.manage): shows "New tax code" (G-01-T13). */
  canManage?: boolean;
  /** URL of a code's editor; default `/o/:org/settings/tax-codes/:id`. */
  editUrl?: (code: TaxCode) => string;
}

export function TaxCodesScreen({ org, canManage = false, editUrl }: TaxCodesScreenProps) {
  const fm = useFormatMessage();
  const ids = useId();
  const [side, setSide] = useState<TaxSide>("sales");
  const [expired, setExpired] = useState(false);
  const [query, setQuery] = useState("");
  const [codes, setCodes] = useState<TaxCode[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    void taxApi.codes(org, { expired }).then((result) => {
      if (cancelled) return;
      if (result.status === 200 && Array.isArray(result.body?.results)) {
        setCodes(result.body.results);
      } else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [org, expired, attempt]);

  const counts = useMemo(() => {
    const live = (codes ?? []).filter((c) => !c.expired);
    return {
      sales: live.filter((c) => c.side === "sales").length,
      purchase: live.filter((c) => c.side === "purchase").length,
    };
  }, [codes]);

  const header = (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex max-w-3xl flex-col gap-1">
        <h1 className="text-2xl font-bold text-fg">{fm(m.title)}</h1>
        <p className="text-sm text-fg-muted">{fm(m.intro)}</p>
        <Link
          href={taxSettingsUrl(org, "default-codes")}
          className="text-sm text-fg underline"
          data-tax-settings-link="default-codes"
        >
          {fm(m.defaultsLink)}
        </Link>
      </div>
      {canManage ? (
        <Link
          href={`/o/${org}/settings/tax-codes/new?side=${side}`}
          className="rounded-md border border-fg bg-surface-accent px-4 py-2 text-sm font-semibold text-fg"
        >
          {fm(m.newCode)}
        </Link>
      ) : null}
    </div>
  );

  if (failed) {
    return (
      <div className="flex flex-col gap-6">
        {header}
        <ErrorState
          title={fm(m.loadFailed)}
          body={fm(m.loadFailedBody)}
          retryLabel={fm(m.retry)}
          onRetry={() => setAttempt((n) => n + 1)}
          headingLevel={2}
        />
      </div>
    );
  }

  const table = (which: TaxSide) => {
    const words = query.trim().toLowerCase();
    const rows = (codes ?? []).filter(
      (c) =>
        c.side === which &&
        (!words || c.code.toLowerCase().includes(words) || c.name.toLowerCase().includes(words)),
    );
    if (codes === null) {
      return (
        <div aria-busy="true">
          <p className="sr-only">{fm(m.loading)}</p>
          <SkeletonText lines={6} />
        </div>
      );
    }
    if (rows.length === 0) return <EmptyState title={fm(m.empty)} headingLevel={2} compact />;
    return (
      <CodesTable
        org={org}
        rows={rows}
        caption={fm(m.table, { side: fm(which === "sales" ? m.sales : m.purchases) })}
        editUrl={editUrl}
      />
    );
  };

  return (
    <div className="flex flex-col gap-6" data-tax-codes="">
      {header}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor={`${ids}-search`} className="sr-only">
            {fm(m.search)}
          </label>
          <Input
            id={`${ids}-search`}
            type="search"
            value={query}
            placeholder={fm(m.search)}
            onChange={(e) => setQuery(e.target.value)}
            className="w-72"
          />
        </div>
        <Switch label={fm(m.showExpired)} checked={expired} onCheckedChange={setExpired} />
      </div>
      <Tabs
        label={fm(m.tabs)}
        value={side}
        onValueChange={(value) => setSide(value as TaxSide)}
        items={[
          {
            value: "sales",
            label: fm(m.sales),
            count: codes ? counts.sales : undefined,
            content: table("sales"),
          },
          {
            value: "purchase",
            label: fm(m.purchases),
            count: codes ? counts.purchase : undefined,
            content: table("purchase"),
          },
        ]}
      />
    </div>
  );
}

function CodesTable({
  org,
  rows,
  caption,
  editUrl,
}: {
  org: string;
  rows: TaxCode[];
  caption: string;
  editUrl?: (code: TaxCode) => string;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const today = Date.now();
  const day = (value: string) => formatDate(value, { locale, timeZone: TIME_ZONE });
  return (
    <table className="w-full border-collapse text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="border-b border-border bg-surface-subtle text-left text-xs text-fg-muted">
          <th scope="col" className="px-3 py-2">
            {fm(m.colCode)}
          </th>
          <th scope="col" className="px-3 py-2">
            {fm(m.colName)}
          </th>
          <th scope="col" className="px-3 py-2">
            {fm(m.colType)}
          </th>
          <th scope="col" className="px-3 py-2">
            {fm(m.colComponents)}
          </th>
          <th scope="col" className="px-3 py-2">
            {fm(m.colEffective)}
          </th>
          <th scope="col" className="px-3 py-2 text-right">
            {fm(m.colUsage)}
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((code) => {
          const left = position(code.effective_from, START);
          const right = position(code.effective_to, END);
          const muted = code.expired || code.archived_at !== null;
          return (
            <tr
              key={code.id}
              className={`border-b border-border ${muted ? "text-fg-muted" : ""}`}
              data-code={code.code}
              data-expired={code.expired || undefined}
            >
              <td className="px-3 py-2 font-mono text-xs">
                {code.code}
                {code.version > 1 || code.expired ? (
                  <span className="ml-1 text-fg-muted">
                    {fm(m.version, { version: code.version })}
                  </span>
                ) : null}
              </td>
              <td className="px-3 py-2">
                <Link
                  href={editUrl ? editUrl(code) : `/o/${org}/settings/tax-codes/${code.id}`}
                  aria-label={fm(m.edit, { name: code.name })}
                  className="hover:underline"
                >
                  {code.name}
                </Link>
                {code.itc_restriction_pct ? (
                  <span className="ml-2 text-xs text-fg-muted">
                    {fm(m.claimable, { pct: code.itc_restriction_pct })}
                  </span>
                ) : null}
              </td>
              <td className="px-3 py-2">
                <div className="flex flex-wrap gap-1">
                  <Badge tone={muted ? "neutral" : TONES[code.type]}>
                    {fm(typeLabels[code.type])}
                  </Badge>
                  {code.expired ? <Badge tone="neutral">{fm(m.expired)}</Badge> : null}
                  {code.archived_at ? <Badge tone="neutral">{fm(m.archived)}</Badge> : null}
                </div>
              </td>
              <td className="px-3 py-2 text-xs">
                {code.components.length
                  ? code.components.map((c) => `${c.name} ${c.rate} %`).join(" · ")
                  : fm(m.noComponents)}
              </td>
              <td className="px-3 py-2">
                <div
                  className="relative h-1.5 w-48 rounded bg-surface-muted"
                  aria-hidden="true"
                  data-timeline=""
                >
                  <div
                    className={`absolute top-0 h-1.5 rounded ${muted ? "bg-fg-muted" : "bg-fg"}`}
                    style={{ insetInlineStart: `${left}%`, width: `${Math.max(1, right - left)}%` }}
                  />
                  <div
                    className="absolute -top-1 h-3.5 w-px bg-fg-danger"
                    style={{ insetInlineStart: `${position(null, today)}%` }}
                  />
                </div>
                <span className="text-xs text-fg-muted">
                  {code.effective_to
                    ? fm(m.range, { start: day(code.effective_from), end: day(code.effective_to) })
                    : fm(m.from, { start: day(code.effective_from) })}
                </span>
              </td>
              <td className="px-3 py-2 text-right text-xs text-fg-muted">
                {fm(m.usage, { count: code.usage_count })}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
