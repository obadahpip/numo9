"use client";

/**
 * Purchase order list (E-01-T13): tabs per status — All, Draft, Awaiting approval, Approved,
 * **Partially received**, **Received**, Billed, Closed, Cancelled — each with its count from the
 * server (the same search applies to the counts), a search box, and per row "Receive" (approved
 * or partially received) and **"Create bill"** (approved, partially received or received: a
 * draft bill of what was received and isn't billed yet, E-02-T08), which opens the bill.
 */
import {
  Badge,
  Button,
  ErrorState,
  Input,
  SkeletonTable,
  Tabs,
  formatDate,
  formatMoney,
  type AppLocale,
  type BadgeTone,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { billUrl } from "../BillEditor";
import {
  PO_STATUSES,
  purchaseOrdersApi,
  type PurchaseOrderList as ListBody,
  type PurchaseOrderRow,
  type PurchaseOrderStatus,
} from "./api";
import { list as m, statusLabels } from "./messages";
import { orderUrl } from "./PurchaseOrderEditor";

export const TONES: Record<PurchaseOrderStatus, BadgeTone> = {
  draft: "neutral",
  awaiting_approval: "warning",
  approved: "info",
  partially_received: "accent",
  received: "success",
  billed: "success",
  closed: "neutral",
  cancelled: "neutral",
};
const RECEIVABLE: readonly PurchaseOrderStatus[] = ["approved", "partially_received"];
export const BILLABLE: readonly PurchaseOrderStatus[] = [
  "approved",
  "partially_received",
  "received",
];

/** The "All" count: every status. */
export function allCount(counts: Partial<Record<PurchaseOrderStatus, number>>): number {
  return PO_STATUSES.reduce((sum, key) => sum + (counts[key] ?? 0), 0);
}

export interface PurchaseOrderListProps {
  org: string;
  navigate?: (href: string) => void;
}

export function PurchaseOrderList({ org, navigate }: Readonly<PurchaseOrderListProps>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [tab, setTab] = useState<"all" | PurchaseOrderStatus>("all");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [body, setBody] = useState<ListBody | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState("");

  const load = useCallback(async () => {
    const result = await purchaseOrdersApi.list(org, {
      status: tab === "all" ? undefined : tab,
      q: query.trim() || undefined,
      page,
    });
    if (result.status === 200 && Array.isArray(result.body.results)) {
      setBody(result.body);
      setFailed(false);
    } else setFailed(true);
  }, [org, tab, query, page]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), query ? 250 : 0);
    return () => clearTimeout(timer);
  }, [load, query]);

  const go = (href: string) => {
    if (navigate) navigate(href);
    else window.location.assign(href);
  };

  const createBill = async (row: PurchaseOrderRow) => {
    setBusy(row.id);
    setProblem("");
    const result = await purchaseOrdersApi.billFromOrder(org, row.id);
    setBusy(null);
    if (result.status === 201 && result.body.id) go(billUrl(org, result.body.id));
    else setProblem(result.body?.detail ?? fm(m.billFailed));
  };

  if (failed) {
    return (
      <ErrorState title={fm(m.loadFailed)} retryLabel={fm(m.retry)} onRetry={() => void load()} />
    );
  }

  const counts = body?.counts ?? ({} as Partial<Record<PurchaseOrderStatus, number>>);
  const head = "px-3 py-2 text-start text-xs font-semibold text-fg-muted";
  const table = !body ? (
    <SkeletonTable rows={5} columns={6} />
  ) : body.results.length === 0 ? (
    <p className="p-6 text-center text-sm text-fg-muted">{fm(m.empty)}</p>
  ) : (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-sm" aria-labelledby={`${ids}-title`}>
        <thead className="bg-surface-muted">
          <tr>
            <th scope="col" className={head}>
              {fm(m.number)}
            </th>
            <th scope="col" className={head}>
              {fm(m.supplier)}
            </th>
            <th scope="col" className={head}>
              {fm(m.date)}
            </th>
            <th scope="col" className={head}>
              {fm(m.delivery)}
            </th>
            <th scope="col" className={`${head} text-end`}>
              {fm(m.total)}
            </th>
            <th scope="col" className={head}>
              {fm(m.status)}
            </th>
            <th scope="col" className={head}>
              {fm(m.actions)}
            </th>
          </tr>
        </thead>
        <tbody>
          {body.results.map((row) => {
            const number = row.number || fm(m.draft);
            return (
              <tr key={row.id} className="border-t border-border" data-po={row.status}>
                <th scope="row" className="px-3 py-2 text-start font-medium">
                  <a href={orderUrl(org, row.id)} className="text-fg underline">
                    {number}
                  </a>
                </th>
                <td className="px-3 py-2">{row.supplier.name}</td>
                <td className="px-3 py-2 tabular-nums">{formatDate(row.date, { locale })}</td>
                <td className="px-3 py-2 tabular-nums">
                  {row.delivery_date ? formatDate(row.delivery_date, { locale }) : ""}
                </td>
                <td className="px-3 py-2 text-end tabular-nums">
                  {formatMoney(row.total, { locale })}
                </td>
                <td className="px-3 py-2">
                  <Badge tone={TONES[row.status]}>{fm(statusLabels[row.status])}</Badge>
                </td>
                <td className="flex flex-wrap gap-2 px-3 py-2">
                  {RECEIVABLE.includes(row.status) ? (
                    <a
                      href={`${orderUrl(org, row.id)}/receive`}
                      className="rounded-md border border-border px-2 py-1 text-xs font-medium text-fg"
                    >
                      {fm(m.receive, { number })}
                    </a>
                  ) : null}
                  {BILLABLE.includes(row.status) ? (
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={busy !== null}
                      onClick={() => void createBill(row)}
                    >
                      {fm(m.createBill, { number })}
                    </Button>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  const items = (["all", ...PO_STATUSES] as const).map((value) => ({
    value,
    label: value === "all" ? fm(m.all) : fm(statusLabels[value]),
    count: body ? (value === "all" ? allCount(counts) : (counts[value] ?? 0)) : undefined,
    content: value === tab ? table : null,
  }));

  return (
    <section aria-labelledby={`${ids}-title`} className="flex flex-col gap-4" data-po-list="">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 id={`${ids}-title`} className="text-2xl font-semibold text-fg">
          {fm(m.title)}
        </h1>
        <div className="flex flex-wrap gap-3">
          <a
            href={`/o/${org}/purchases/commitments`}
            className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-fg"
          >
            {fm(m.commitments)}
          </a>
          <a
            href={`/o/${org}/purchases/orders/new`}
            className="rounded-md bg-surface-accent px-3 py-1.5 text-sm font-medium text-fg-inverse"
          >
            {fm(m.newOrder)}
          </a>
        </div>
      </div>
      <label className="flex max-w-md flex-col gap-1 text-sm font-medium text-fg">
        {fm(m.search)}
        <Input
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(1);
          }}
        />
      </label>
      {problem ? (
        <p role="alert" className="text-sm font-semibold text-fg-danger">
          {problem}
        </p>
      ) : null}
      <Tabs
        items={items}
        value={tab}
        onValueChange={(value) => {
          setTab(value as typeof tab);
          setPage(1);
        }}
        label={fm(m.tabs)}
      />
      {body && body.pages > 1 ? (
        <nav
          className="flex items-center gap-3 text-sm"
          aria-label={fm(m.more, { page: body.page, pages: body.pages })}
        >
          <Button
            size="sm"
            variant="secondary"
            disabled={page <= 1}
            onClick={() => setPage((n) => n - 1)}
          >
            {fm(m.previous)}
          </Button>
          <span>{fm(m.more, { page: body.page, pages: body.pages })}</span>
          <Button
            size="sm"
            variant="secondary"
            disabled={page >= body.pages}
            onClick={() => setPage((n) => n + 1)}
          >
            {fm(m.next)}
          </Button>
        </nav>
      ) : null}
    </section>
  );
}
