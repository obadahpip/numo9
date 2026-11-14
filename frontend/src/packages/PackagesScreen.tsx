"use client";

import {
  Button,
  EmptyState,
  ExplainPanel,
  LoadingRegion,
  SkeletonTable,
  StatusBadge,
  type AppLocale,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { packagesApi, type ApiError, type PlatformPackage } from "./api";
import { pm } from "./messages";
import { money } from "./money";

export const packageUrl = (code: string) => `/console/packages/${encodeURIComponent(code)}`;
export const NEW_PACKAGE_URL = "/console/packages/new";

/**
 * Platform console → Packages and prices (U-02-T09), `/console/packages`: every package with
 * its status, products, prices in force today and subscriber count; "New package" opens the
 * editor. Platform owner only (the API's 403 shows the refusal panel).
 */
export function PackagesScreen() {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [packages, setPackages] = useState<PlatformPackage[] | null>(null);
  const [refusal, setRefusal] = useState<ApiError | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    void packagesApi.list().then(({ status, body }) => {
      if (status === 401 || status === 403) setRefusal(body as ApiError);
      else if (status !== 200 || !("packages" in body)) setFailed(true);
      else setPackages((body as { packages: PlatformPackage[] }).packages);
    });
  }, []);

  if (refusal) {
    return (
      <ExplainPanel
        kind="permission"
        headingLevel={1}
        title={fm(pm.refusedTitle)}
        body={<p>{refusal.detail}</p>}
      />
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold">{fm(pm.title)}</h1>
          <p className="text-fg-muted">{fm(pm.intro)}</p>
        </div>
        {packages && packages.length > 0 ? (
          <Button asChild>
            <Link href={NEW_PACKAGE_URL}>{fm(pm.newPackage)}</Link>
          </Button>
        ) : null}
      </header>
      {failed ? (
        <p role="alert" className="text-fg-danger">
          {fm(pm.loadFailed)}
        </p>
      ) : null}
      {packages === null && !failed ? (
        <LoadingRegion label={fm(pm.loading)}>
          <SkeletonTable rows={4} columns={6} />
        </LoadingRegion>
      ) : null}
      {packages && packages.length === 0 ? (
        <EmptyState
          title={fm(pm.emptyTitle)}
          body={fm(pm.emptyBody)}
          actions={[
            <Button key="create" asChild>
              <Link href={NEW_PACKAGE_URL}>{fm(pm.createFirst)}</Link>
            </Button>,
          ]}
        />
      ) : null}
      {packages && packages.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-start text-sm">
            <caption className="sr-only">{fm(pm.title)}</caption>
            <thead className="bg-surface-muted text-fg-muted">
              <tr>
                <th scope="col" className="px-4 py-2 text-start font-medium">
                  {fm(pm.colPackage)}
                </th>
                <th scope="col" className="px-4 py-2 text-start font-medium">
                  {fm(pm.colStatus)}
                </th>
                <th scope="col" className="px-4 py-2 text-start font-medium">
                  {fm(pm.colProducts)}
                </th>
                <th scope="col" className="px-4 py-2 text-end font-medium">
                  {fm(pm.colMonthly)}
                </th>
                <th scope="col" className="px-4 py-2 text-end font-medium">
                  {fm(pm.colAnnual)}
                </th>
                <th scope="col" className="px-4 py-2 text-end font-medium">
                  {fm(pm.colSubscribers)}
                </th>
              </tr>
            </thead>
            <tbody>
              {packages.map((p) => (
                <tr key={p.code} data-package={p.code} className="border-t border-border">
                  <td className="px-4 py-2">
                    <Link
                      href={packageUrl(p.code)}
                      aria-label={fm(pm.open, { name: p.name })}
                      className="font-medium underline-offset-2 hover:underline"
                    >
                      {p.name}
                    </Link>
                    <div className="font-mono text-xs text-fg-muted">{p.code}</div>
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge status={p.status} label={p.status_label} />
                  </td>
                  <td className="px-4 py-2">{p.products.map((x) => x.name).join(", ")}</td>
                  {(["month", "year"] as const).map((interval) => {
                    const price = p.current_prices[interval];
                    return (
                      <td key={interval} className="px-4 py-2 text-end tabular-nums">
                        {price ? (
                          money(price.amount_cents, locale)
                        ) : (
                          <span className="text-fg-muted">{fm(pm.noPrice)}</span>
                        )}
                      </td>
                    );
                  })}
                  <td className="px-4 py-2 text-end tabular-nums">{p.subscriber_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
