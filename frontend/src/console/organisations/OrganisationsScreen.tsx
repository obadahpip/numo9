"use client";

/**
 * Console → Organisations (U-06-T03/T04): every organisation with the API's filters (name,
 * status, package, province, created range), newest first, 50 a page; each row opens its detail.
 * Demo organisations are listed, marked "Demo" (metrics leave them out).
 */
import { Button, ErrorState, Input, formatDate, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import Link from "next/link";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { listOrganisations, type OrganisationFilters, type PlatformOrganisationPage } from "./api";
import { m } from "./messages";

const STATUSES = ["", "trial", "active", "grace", "read_only", "cancelled", "demo"];

export function OrganisationsScreen() {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [filters, setFilters] = useState<OrganisationFilters>({ page: 1 });
  const [page, setPage] = useState<PlatformOrganisationPage | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const ids = {
    q: useId(),
    status: useId(),
    pkg: useId(),
    province: useId(),
    from: useId(),
    to: useId(),
  };

  useEffect(() => {
    let cancelled = false;
    void listOrganisations(filters).then((result) => {
      if (cancelled) return;
      if (result.status === 200) {
        setPage(result.body);
        setFailed(false);
      } else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [filters, attempt]);

  const set = (key: keyof OrganisationFilters, value: string) =>
    setFilters((current) => ({ ...current, [key]: value, page: 1 }));
  const label = "text-xs font-semibold text-fg-muted";
  const select =
    "min-h-touch-target rounded-md border border-border-strong bg-surface px-2 text-sm";

  return (
    <div className="flex flex-col gap-4" data-console-organisations="">
      <h1 className="text-2xl font-bold text-fg">{fm(m.title)}</h1>
      <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => e.preventDefault()}>
        <div className="grid gap-1">
          <label htmlFor={ids.q} className={label}>
            {fm(m.search)}
          </label>
          <Input id={ids.q} value={filters.q ?? ""} onChange={(e) => set("q", e.target.value)} />
        </div>
        <div className="grid gap-1">
          <label htmlFor={ids.status} className={label}>
            {fm(m.status)}
          </label>
          <select
            id={ids.status}
            className={select}
            value={filters.status ?? ""}
            onChange={(e) => set("status", e.target.value)}
          >
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {value || fm(m.any)}
              </option>
            ))}
          </select>
        </div>
        <div className="grid gap-1">
          <label htmlFor={ids.pkg} className={label}>
            {fm(m.package)}
          </label>
          <Input
            id={ids.pkg}
            value={filters.package ?? ""}
            onChange={(e) => set("package", e.target.value)}
          />
        </div>
        <div className="grid gap-1">
          <label htmlFor={ids.province} className={label}>
            {fm(m.province)}
          </label>
          <Input
            id={ids.province}
            maxLength={2}
            value={filters.province ?? ""}
            onChange={(e) => set("province", e.target.value)}
          />
        </div>
        <div className="grid gap-1">
          <label htmlFor={ids.from} className={label}>
            {fm(m.createdFrom)}
          </label>
          <Input
            id={ids.from}
            type="date"
            value={filters.created_from ?? ""}
            onChange={(e) => set("created_from", e.target.value)}
          />
        </div>
        <div className="grid gap-1">
          <label htmlFor={ids.to} className={label}>
            {fm(m.createdTo)}
          </label>
          <Input
            id={ids.to}
            type="date"
            value={filters.created_to ?? ""}
            onChange={(e) => set("created_to", e.target.value)}
          />
        </div>
      </form>
      {failed ? (
        <ErrorState
          title={fm(m.loadFailed)}
          retryLabel={fm(m.retry)}
          onRetry={() => setAttempt((n) => n + 1)}
          headingLevel={2}
        />
      ) : null}
      {page ? (
        <>
          <p className="text-sm text-fg-muted" role="status">
            {fm(m.summary, { count: page.count })}
          </p>
          <table className="w-full text-sm" aria-label={fm(m.title)}>
            <thead>
              <tr className="border-b border-border text-start text-xs text-fg-muted">
                <th className="py-2 text-start">{fm(m.name)}</th>
                <th className="py-2 text-start">{fm(m.status)}</th>
                <th className="py-2 text-start">{fm(m.package)}</th>
                <th className="py-2 text-start">{fm(m.province)}</th>
                <th className="py-2 text-start">{fm(m.created)}</th>
              </tr>
            </thead>
            <tbody>
              {page.results.map((row) => (
                <tr key={row.id} className="border-b border-border" data-org={row.id}>
                  <td className="py-2">
                    <Link
                      href={`/console/organisations/${row.id}`}
                      className="font-semibold text-fg underline"
                    >
                      {row.name}
                    </Link>
                    {row.is_demo ? (
                      <span className="ms-2 rounded-full border border-border px-2 text-xs">
                        {fm(m.demo)}
                      </span>
                    ) : null}
                  </td>
                  <td className="py-2">{row.status}</td>
                  <td className="py-2">{row.package || fm(m.none)}</td>
                  <td className="py-2">{row.province || fm(m.none)}</td>
                  <td className="py-2">
                    {formatDate(new Date(row.created_at), { locale, timeZone: "America/Toronto" })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              disabled={page.page <= 1}
              onClick={() => setFilters((c) => ({ ...c, page: (c.page ?? 1) - 1 }))}
            >
              {fm(m.previous)}
            </Button>
            <span className="text-sm">{fm(m.pageOf, { page: page.page, pages: page.pages })}</span>
            <Button
              size="sm"
              disabled={page.page >= page.pages}
              onClick={() => setFilters((c) => ({ ...c, page: (c.page ?? 1) + 1 }))}
            >
              {fm(m.next)}
            </Button>
          </div>
        </>
      ) : null}
    </div>
  );
}
