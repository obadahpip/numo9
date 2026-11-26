"use client";

/**
 * Purchases overview (E-02-T15, gap-22): the shared `OverviewPage` (D-09-T06) — the same component
 * as the sales overview — with the status tiles Draft / Awaiting approval / Awaiting payment /
 * Overdue (count and amount; each opens the bills list on the tab of the same key, whose count it
 * equals: one query source), "Money going out" by age and the suppliers owed the most. Each region
 * loads on its own and fails on its own with Try again and a reference (D-09-T10).
 */
import {
  AgingBar,
  EmptyState,
  formatDate,
  formatMoney,
  OverviewCard,
  OverviewPage,
  OverviewTiles,
  type AppLocale,
  type ShellLinkComponent,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";

import { useFormatMessage } from "@/i18n";
import { cardState, useCardData } from "@/overview/useCardData";
import { orgModuleUrl } from "@/routing/routes";

import { billsApi, type BillTab, type PurchasesOverview } from "./api";
import { AGING_LABEL, om, TAB_LABEL } from "./overviewMessages";

const NextLink: ShellLinkComponent = ({ href, ...props }) => <Link href={href} {...props} />;

export function billsListUrl(org: string, tab: BillTab = "all"): string {
  const list = orgModuleUrl(org, "purchases/bills");
  return tab === "all" ? list : `${list}?tab=${tab}`;
}

export function PurchasesOverviewScreen({ org }: { org: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const tiles = useCardData<PurchasesOverview>(
    (headers) => billsApi.overview(org, "tiles", headers),
    org,
    (r) => r.status === 200 && Array.isArray(r.body?.tiles),
  );
  const aging = useCardData<PurchasesOverview>(
    (headers) => billsApi.overview(org, "aging", headers),
    org,
    (r) => r.status === 200 && Array.isArray(r.body?.aging),
  );
  const suppliers = useCardData<PurchasesOverview>(
    (headers) => billsApi.overview(org, "suppliers", headers),
    org,
    (r) => r.status === 200 && Array.isArray(r.body?.top_suppliers),
  );

  const tileRows = (tiles.data?.tiles ?? []).map((tile) => ({
    key: tile.key,
    label: fm(TAB_LABEL[tile.key]),
    count: tile.count,
    amount: tile.amount,
    href: billsListUrl(org, tile.key),
    tone: tile.key === "overdue" ? ("attention" as const) : ("default" as const),
  }));
  const empty = tiles.status === "ready" && tileRows.every((t) => t.count === 0);

  const tilesRegion =
    tiles.status === "error" ? (
      <OverviewCard cardKey="tiles" {...cardState(fm, fm(om.tilesCard), tiles)} />
    ) : (
      <OverviewTiles
        tiles={tileRows}
        loading={tiles.status === "loading"}
        locale={locale}
        linkComponent={NextLink}
        tileLabel={(tile, _count, amount) =>
          fm(om.tile, { label: tile.label, count: tile.count, amount })
        }
      />
    );

  return (
    <OverviewPage
      kind="purchases"
      title={fm(om.title)}
      intro={fm(om.intro)}
      actions={
        <>
          <Link
            href={billsListUrl(org)}
            className="inline-flex min-h-touch-target items-center px-2 text-sm font-semibold text-fg underline"
          >
            {fm(om.allBills)}
          </Link>
          <Link
            href={`${orgModuleUrl(org, "purchases/bills")}/new`}
            className="inline-flex min-h-touch-target items-center rounded-md bg-surface-accent px-4 text-sm font-semibold text-fg-on-accent hover:bg-surface-accent-hover"
          >
            {fm(om.newBill)}
          </Link>
        </>
      }
      tiles={
        <div className="flex flex-col gap-2">
          {tilesRegion}
          {tiles.data?.as_of ? (
            <p className="text-xs text-fg-muted">
              {fm(om.asOf, { date: formatDate(tiles.data.as_of, { locale }) })}
            </p>
          ) : null}
          {empty ? (
            <EmptyState
              compact
              title={fm(om.emptyTitle)}
              body={fm(om.emptyBody)}
              actions={[
                <Link
                  key="new"
                  href={`${orgModuleUrl(org, "purchases/bills")}/new`}
                  className="font-semibold underline"
                >
                  {fm(om.newBill)}
                </Link>,
              ]}
            />
          ) : null}
        </div>
      }
    >
      <OverviewCard cardKey="aging" wide {...cardState(fm, fm(om.agingCard), aging)}>
        <AgingBar
          locale={locale}
          linkComponent={NextLink}
          labels={{
            chart: (total) => fm(om.agingChart, { total }),
            empty: fm(om.agingEmpty),
          }}
          buckets={(aging.data?.aging ?? []).map((bucket) => ({
            key: bucket.key,
            label: AGING_LABEL[bucket.key] ? fm(AGING_LABEL[bucket.key]!) : bucket.label,
            amount: bucket.amount,
            href:
              bucket.count > 0
                ? billsListUrl(org, bucket.key === "current" ? "awaiting_payment" : "overdue")
                : undefined,
          }))}
        />
      </OverviewCard>
      <OverviewCard
        cardKey="suppliers"
        {...cardState(fm, fm(om.suppliersCard), suppliers)}
        action={
          <Link href={billsListUrl(org, "awaiting_payment")} className="text-sm underline">
            {fm(om.allBills)}
          </Link>
        }
      >
        {(suppliers.data?.top_suppliers ?? []).length === 0 ? (
          <p className="text-sm text-fg-muted">{fm(om.suppliersEmpty)}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border text-sm">
            {(suppliers.data?.top_suppliers ?? []).map((supplier) => (
              <li key={supplier.id} className="flex items-start justify-between gap-3 py-2">
                <span className="flex flex-col">
                  <Link
                    href={`${orgModuleUrl(org, "contacts")}/${supplier.id}`}
                    className="font-semibold text-fg underline"
                  >
                    {supplier.name}
                  </Link>
                  <span className="text-fg-muted">
                    {fm(om.supplierBills, { count: supplier.bills })}
                  </span>
                </span>
                <span className="flex flex-col items-end tabular-nums">
                  <span className="text-fg">{formatMoney(supplier.owed, { locale })}</span>
                  {Number(supplier.overdue) > 0 ? (
                    <span className="text-fg-danger">
                      {fm(om.supplierOverdue, {
                        amount: formatMoney(supplier.overdue, { locale }),
                      })}
                    </span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        )}
      </OverviewCard>
    </OverviewPage>
  );
}
