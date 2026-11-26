"use client";

/**
 * Bills list (E-02-T15): tabs All / Draft / Awaiting approval / Awaiting payment / Overdue / Paid /
 * Void, each with its count — the same numbers as the purchases overview tiles (one query
 * source, `purchases.overview` on the server). Server-side search and pages of 50 (large lists);
 * a row opens the bill. `?tab=` opens a tab directly (the overview tiles link here).
 */
import {
  Button,
  DataGrid,
  EmptyState,
  ErrorState,
  formatDate,
  formatMoney,
  StatusBadge,
  Tabs,
  EMPTY_VIEW,
  type AppLocale,
  type DataGridColumn,
  type DataGridLabels,
  type DataGridStatus,
  type GridViewState,
  type StatusKey,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useMemo, useState } from "react";

import { lm } from "@/contacts/listMessages";
import { useFormatMessage } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

import {
  BILL_TABS,
  billsApi,
  isBillTab,
  type BillList,
  type BillRow,
  type BillStatus,
  type BillTab,
} from "./api";
import { om, TAB_LABEL } from "./overviewMessages";

const BADGE: Record<BillStatus, StatusKey> = {
  draft: "draft",
  awaiting_approval: "awaiting_approval",
  awaiting_payment: "approved",
  partially_paid: "partially_paid",
  paid: "paid",
  void: "voided",
};

function useLabels(): DataGridLabels {
  const fm = useFormatMessage();
  return {
    grid: fm(om.grid),
    search: fm(om.search),
    columns: fm(lm.columns),
    density: fm(lm.density),
    comfortable: fm(lm.comfortable),
    compact: fm(lm.compact),
    filterAll: fm(lm.all),
    filterChip: (column, value) => fm(lm.chip, { column, value }),
    clearFilters: fm(lm.clear),
    selectAll: fm(lm.selectAll),
    selectRow: (row) => fm(lm.selectRow, { row }),
    selectedCount: (count) => fm(lm.selected, { count }),
    clearSelection: fm(lm.clearSelection),
    resultCount: (shown, total) => fm(om.results, { shown, total }),
    loading: fm(om.loading),
  };
}

export function BillsListScreen({
  org,
  initialTab = "all",
}: {
  org: string;
  initialTab?: BillTab;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const labels = useLabels();
  const [tab, setTab] = useState<BillTab>(initialTab);
  const [view, setView] = useState<GridViewState>(EMPTY_VIEW);
  const [page, setPage] = useState(1);
  const [list, setList] = useState<BillList | null>(null);
  const [status, setStatus] = useState<DataGridStatus>("loading");
  const [attempt, setAttempt] = useState(0);
  const search = view.search;

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    const timer = setTimeout(
      () => {
        void billsApi.list(org, { tab, q: search, page }).then((result) => {
          if (cancelled) return;
          if (result.status === 200 && Array.isArray(result.body?.results)) {
            setList(result.body);
            setStatus("ready");
          } else setStatus("error");
        });
      },
      search ? 250 : 0,
    );
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [org, tab, search, page, attempt]);

  const columns = useMemo<DataGridColumn<BillRow>[]>(
    () => [
      {
        id: "number",
        header: fm(om.colNumber),
        accessor: (row) => row.number,
        hideable: false,
        cell: (row) => (
          <Link
            href={row.url}
            className="font-semibold text-fg underline"
            onClick={(event) => event.stopPropagation()}
          >
            {row.number || fm(om.draftNumber)}
          </Link>
        ),
      },
      { id: "supplier", header: fm(om.colSupplier), accessor: (row) => row.supplier.name },
      {
        id: "supplier_invoice_no",
        header: fm(om.colSupplierInvoice),
        accessor: (row) => row.supplier_invoice_no,
      },
      {
        id: "date",
        header: fm(om.colDate),
        accessor: (row) => row.date,
        cell: (row) => formatDate(row.date, { locale }),
        width: 130,
      },
      {
        id: "due_date",
        header: fm(om.colDue),
        accessor: (row) => row.due_date,
        cell: (row) => (row.due_date ? formatDate(row.due_date, { locale }) : ""),
        width: 130,
      },
      {
        id: "status",
        header: fm(om.colStatus),
        accessor: (row) => row.status_label,
        cell: (row) => <StatusBadge status={BADGE[row.status]} label={row.status_label} />,
        width: 170,
      },
      {
        id: "total",
        header: fm(om.colTotal),
        accessor: (row) => row.total,
        cell: (row) => formatMoney(row.total, { locale }),
        align: "end",
        width: 130,
      },
      {
        id: "amount_due",
        header: fm(om.colDueAmount),
        accessor: (row) => row.amount_due,
        cell: (row) => formatMoney(row.amount_due, { locale }),
        align: "end",
        width: 130,
      },
    ],
    [fm, locale],
  );

  const counts = new Map((list?.tabs ?? []).map((t) => [t.key, t.count]));
  const pages = list?.pages ?? 1;

  const grid = (
    <div className="flex flex-col gap-3">
      <DataGrid
        manual
        data={list?.results ?? []}
        totalCount={list?.count}
        columns={columns}
        getRowId={(row) => row.id}
        getRowLabel={(row) => row.number || row.supplier.name}
        labels={labels}
        status={status}
        view={view}
        onViewChange={(next) => {
          if (next.search !== view.search) setPage(1);
          setView(next);
        }}
        searchPlaceholder={fm(om.search)}
        onRowOpen={(row) => window.location.assign(row.url)}
        emptyState={<EmptyState title={fm(om.empty)} body={fm(om.tabEmptyBody)} compact />}
        noResultsState={<EmptyState title={fm(om.noResults)} compact />}
        errorState={
          <ErrorState
            title={fm(om.failed)}
            retryLabel={fm(om.retry)}
            onRetry={() => setAttempt((n) => n + 1)}
          />
        }
      />
      {pages > 1 ? (
        <nav
          className="flex items-center justify-end gap-2"
          aria-label={fm(om.pageOf, { page, pages })}
        >
          <Button size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            {fm(om.previous)}
          </Button>
          <span className="text-sm text-fg-muted">{fm(om.pageOf, { page, pages })}</span>
          <Button size="sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
            {fm(om.next)}
          </Button>
        </nav>
      ) : null}
    </div>
  );

  return (
    <div className="flex flex-col gap-4" data-bills-list="">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <h1 className="text-2xl font-bold text-fg">{fm(om.listTitle)}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            href={orgModuleUrl(org, "purchases")}
            className="inline-flex min-h-touch-target items-center px-2 text-sm font-semibold text-fg underline"
          >
            {fm(om.overviewLink)}
          </Link>
          <Link
            href={`${orgModuleUrl(org, "purchases/bills")}/new`}
            className="inline-flex min-h-touch-target items-center rounded-md bg-surface-accent px-4 text-sm font-semibold text-fg-on-accent hover:bg-surface-accent-hover"
          >
            {fm(om.newBill)}
          </Link>
        </div>
      </header>
      <Tabs
        label={fm(om.tabs)}
        value={tab}
        onValueChange={(value) => {
          if (!isBillTab(value)) return;
          setTab(value);
          setPage(1);
          const url = new URL(window.location.href);
          if (value === "all") url.searchParams.delete("tab");
          else url.searchParams.set("tab", value);
          window.history.replaceState(null, "", url.toString());
        }}
        items={BILL_TABS.map((value) => ({
          value,
          label: fm(TAB_LABEL[value]),
          count: counts.get(value),
          content: value === tab ? grid : null,
        }))}
      />
    </div>
  );
}
