"use client";

/**
 * Overview page (D-09-T06): the one overview pattern for sales **and** purchases (gap-22: Xero has
 * a modern sales overview and a legacy purchases one — Numo9 has one component, one id).
 *
 * - **Status tiles** — Draft / Awaiting approval / Awaiting payment / **Overdue**: the count and
 *   the amount of each, the whole tile a link to the list filtered the same way (tile counts come
 *   from the list's own query, so the tile and the tab always agree). Zero shows `0` and `$0.00`,
 *   never a blank or a dash.
 * - **Cards** — independent regions (money coming in / going out, top contacts owing, quotes …),
 *   each with its own loading skeleton and its own error with **Try again**: one failing card
 *   never blanks the page.
 * - **Aging bar** — what is owed by age (current, 1–30, 31–60, 61–90, over 90 days): one
 *   horizontal stacked bar on a single-hue ramp that darkens with age, 2 px gaps between
 *   segments, and every bucket named with its amount in the legend below (never colour alone).
 *
 * Every text comes from the caller (`labels`, titles): the component holds no copy of its own.
 * The root carries `data-component="overview-page"` and `data-overview="<kind>"`.
 */
import type { ReactNode } from "react";

import { formatMoney, formatNumber, type Amount } from "../format/format";
import type { AppLocale } from "../format/locale";
import { cn } from "../primitives/cn";
import type { ShellLinkComponent } from "../shell/AppShell";
import { ErrorState } from "../states/ErrorState";
import { LoadingRegion, Skeleton, SkeletonText } from "../states/Skeleton";

/** The component id shared by every overview screen (gap-22 visual-regression anchor). */
export const OVERVIEW_COMPONENT_ID = "overview-page";

const DefaultLink: ShellLinkComponent = (props) => <a {...props} />;

// ---- tiles -------------------------------------------------------------------------------------

export interface OverviewTile {
  /** `draft`, `awaiting_approval`, `awaiting_payment`, `overdue` … (also the list tab). */
  key: string;
  label: string;
  count: number;
  amount: Amount;
  /** The list filtered like the tile (its count equals the tile's). */
  href: string;
  /** `attention`: drawn with the danger accent (Overdue with a count above 0). */
  tone?: "default" | "attention";
}

export interface OverviewTilesProps {
  tiles: OverviewTile[];
  locale: AppLocale;
  /** Accessible name of one tile's link, e.g. (tile) → "Overdue: 3 invoices, $1,250.00". */
  tileLabel: (tile: OverviewTile, count: string, amount: string) => string;
  linkComponent?: ShellLinkComponent;
  /** Tiles still loading: same layout, skeleton numbers. */
  loading?: boolean;
  /** How many skeleton tiles to show while loading (default 4). */
  placeholders?: number;
}

export function OverviewTiles({
  tiles,
  locale,
  tileLabel,
  linkComponent: Link = DefaultLink,
  loading = false,
  placeholders = 4,
}: OverviewTilesProps) {
  if (loading) {
    return (
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-hidden="true">
        {Array.from({ length: placeholders }, (_, i) => (
          <li key={i} className="rounded-lg border border-border bg-surface p-4">
            <Skeleton width="50%" />
            <span className="mt-3 block">
              <Skeleton width="30%" height="1.75rem" />
            </span>
            <span className="mt-2 block">
              <Skeleton width="40%" />
            </span>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4" data-overview-tiles="">
      {tiles.map((tile) => {
        const count = formatNumber(tile.count, { locale, maximumFractionDigits: 0 });
        const amount = formatMoney(tile.amount, { locale });
        const attention = tile.tone === "attention" && tile.count > 0;
        return (
          <li key={tile.key}>
            <Link
              href={tile.href}
              data-tile={tile.key}
              aria-label={tileLabel(tile, count, amount)}
              className={cn(
                "flex h-full flex-col gap-1 rounded-lg border bg-surface p-4 text-left",
                "hover:bg-surface-subtle focus-visible:outline-2 focus-visible:outline-offset-2",
                attention ? "border-border-danger" : "border-border",
              )}
            >
              <span className={cn("text-sm", attention ? "text-fg-danger" : "text-fg-muted")}>
                {tile.label}
              </span>
              <span className="text-2xl font-semibold text-fg tabular-nums">{count}</span>
              <span className="text-sm text-fg tabular-nums">{amount}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

// ---- cards -------------------------------------------------------------------------------------

export type OverviewCardStatus = "loading" | "ready" | "error";

/**
 * A card's failure (D-09-T10): never a bare "Unable to load" — it names what failed, says what to
 * do, offers **Try again** and shows the support reference (the request's `X-Request-ID`).
 */
export interface OverviewCardError {
  /** What failed, naming the thing: "Money coming in couldn't be loaded". */
  title: string;
  /** Why (if known) and what to do. */
  body?: ReactNode;
  /** Support reference of the failed request, shown as `labels.reference(ref)`. */
  reference?: string;
}

export interface OverviewCardLabels {
  /** Announced while the card loads: "Loading money coming in…". */
  loading: string;
  retry: string;
  /** e.g. (ref) → "Reference: web-7f3c2a10". */
  reference: (reference: string) => string;
}

interface OverviewCardBase {
  /** Card heading (also its region's accessible name). */
  title: string;
  /** Key for tests and the visual id (`data-card`). */
  cardKey: string;
  labels: OverviewCardLabels;
  retrying?: boolean;
  /** Link beside the heading ("View all"). */
  action?: ReactNode;
  /** Two-column-wide card on large screens. */
  wide?: boolean;
  children?: ReactNode;
}

/** A failed card must say what failed and how to retry (the type refuses a silent error). */
export type OverviewCardState =
  | { status: "loading" | "ready"; error?: undefined; onRetry?: () => void }
  | { status: "error"; error: OverviewCardError; onRetry: () => void };

export type OverviewCardProps = OverviewCardBase & OverviewCardState;

export function OverviewCard({
  title,
  cardKey,
  status,
  labels,
  error,
  onRetry,
  retrying = false,
  action,
  wide = false,
  children,
}: OverviewCardProps) {
  const headingId = `overview-card-${cardKey}`;
  return (
    <section
      aria-labelledby={headingId}
      data-card={cardKey}
      data-card-status={status}
      aria-busy={status === "loading" || undefined}
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-border bg-surface p-4",
        wide && "lg:col-span-2",
      )}
    >
      <div className="flex items-baseline justify-between gap-3">
        <h2 id={headingId} className="text-base font-semibold text-fg">
          {title}
        </h2>
        {status === "ready" ? action : null}
      </div>
      {status === "loading" ? (
        <LoadingRegion label={labels.loading}>
          <SkeletonText lines={3} />
        </LoadingRegion>
      ) : status === "error" ? (
        <ErrorState
          headingLevel={3}
          className="py-4"
          title={error?.title ?? title}
          body={error?.body}
          retryLabel={labels.retry}
          onRetry={onRetry ?? (() => undefined)}
          retrying={retrying}
          reference={error?.reference}
          referenceLabel={labels.reference}
        />
      ) : (
        children
      )}
    </section>
  );
}

// ---- aging bar ---------------------------------------------------------------------------------

export interface AgingBucket {
  /** `current`, `1_30`, `31_60`, `61_90`, `over_90`. */
  key: string;
  label: string;
  amount: Amount;
  /** The list filtered to this bucket, when there is one. */
  href?: string;
}

/** Fills of the buckets, youngest to oldest: one hue (neutral ink) darkening with age. */
export const AGING_STEPS = [
  "var(--color-neutral-200)",
  "var(--color-neutral-300)",
  "var(--color-neutral-500)",
  "var(--color-neutral-700)",
  "var(--color-neutral-900)",
] as const;

export interface AgingBarLabels {
  /** Accessible name of the bar: "Money coming in by age: $12,400.00 owed". */
  chart: (total: string) => string;
  /** Text when nothing is owed: "Nothing owed — every invoice is paid." */
  empty: string;
}

export interface AgingBarProps {
  buckets: AgingBucket[];
  locale: AppLocale;
  labels: AgingBarLabels;
  linkComponent?: ShellLinkComponent;
}

function cents(amount: Amount): number {
  const value = Number(amount);
  return Number.isFinite(value) && value > 0 ? value : 0;
}

/** The total of the buckets as a decimal string (exact to the cent). */
export function agingTotal(buckets: AgingBucket[]): string {
  let total = 0n;
  for (const bucket of buckets) {
    const [whole = "0", fraction = ""] = String(bucket.amount).replace("-", "").split(".");
    const sign = String(bucket.amount).startsWith("-") ? -1n : 1n;
    total += sign * (BigInt(whole || "0") * 100n + BigInt((fraction + "00").slice(0, 2)));
  }
  const negative = total < 0n;
  const absolute = negative ? -total : total;
  const text = `${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
  return negative ? `-${text}` : text;
}

export function AgingBar({
  buckets,
  locale,
  labels,
  linkComponent: Link = DefaultLink,
}: AgingBarProps) {
  const total = agingTotal(buckets);
  const sum = buckets.reduce((acc, b) => acc + cents(b.amount), 0);
  const formattedTotal = formatMoney(total, { locale });
  return (
    <figure className="flex flex-col gap-3" data-aging-bar="">
      <div
        role="img"
        aria-label={labels.chart(formattedTotal)}
        className="flex h-3 w-full gap-0.5 overflow-hidden rounded bg-surface-muted"
      >
        {sum > 0
          ? buckets.map((bucket, i) =>
              cents(bucket.amount) > 0 ? (
                <span
                  key={bucket.key}
                  data-bucket={bucket.key}
                  className="h-full first:rounded-l last:rounded-r"
                  style={{
                    width: `${(cents(bucket.amount) / sum) * 100}%`,
                    background: AGING_STEPS[Math.min(i, AGING_STEPS.length - 1)],
                  }}
                />
              ) : null,
            )
          : null}
      </div>
      {sum > 0 ? null : <p className="text-sm text-fg-muted">{labels.empty}</p>}
      <figcaption>
        <ul className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-5">
          {buckets.map((bucket, i) => {
            const amount = formatMoney(bucket.amount, { locale });
            const body = (
              <>
                <span className="flex items-center gap-1.5 text-fg-muted">
                  <span
                    aria-hidden="true"
                    className="inline-block size-2.5 rounded-sm"
                    style={{ background: AGING_STEPS[Math.min(i, AGING_STEPS.length - 1)] }}
                  />
                  {bucket.label}
                </span>
                <span className="text-fg tabular-nums">{amount}</span>
              </>
            );
            return (
              <li key={bucket.key} data-bucket-legend={bucket.key} className="flex flex-col">
                {bucket.href ? (
                  <Link href={bucket.href} className="flex flex-col hover:underline">
                    {body}
                  </Link>
                ) : (
                  body
                )}
              </li>
            );
          })}
        </ul>
      </figcaption>
    </figure>
  );
}

// ---- page --------------------------------------------------------------------------------------

export interface OverviewPageProps {
  /** `sales`, `purchases` — which overview this is (`data-overview`). */
  kind: string;
  title: string;
  /** Short line under the title. */
  intro?: ReactNode;
  /** Primary actions beside the title ("New invoice"). */
  actions?: ReactNode;
  /** The status tiles (usually `OverviewTiles`, or its error card). */
  tiles: ReactNode;
  /** The cards (`OverviewCard`s), laid out two columns wide on large screens. */
  children?: ReactNode;
  className?: string;
}

export function OverviewPage({
  kind,
  title,
  intro,
  actions,
  tiles,
  children,
  className,
}: OverviewPageProps) {
  return (
    <div
      data-component={OVERVIEW_COMPONENT_ID}
      data-overview={kind}
      className={cn("flex flex-col gap-6", className)}
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex max-w-3xl flex-col gap-1">
          <h1 className="text-2xl font-bold text-fg">{title}</h1>
          {intro ? <p className="text-sm text-fg-muted">{intro}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </header>
      {tiles}
      {children ? <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">{children}</div> : null}
    </div>
  );
}
