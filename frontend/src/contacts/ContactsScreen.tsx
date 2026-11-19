"use client";

/**
 * Contacts list (B-01-T14): role tabs whose title names the list (gap-19: "Customers",
 * "Suppliers"…, with counts), search, column chooser and density (DataGrid), saved views (this
 * browser), archive / restore of the selected contacts. A name opens the contact; "New contact"
 * opens the form (B-01-T15).
 */
import {
  Button,
  DataGrid,
  EmptyState,
  ErrorState,
  Input,
  localSavedViewsStore,
  Select,
  Tabs,
  useSavedViews,
  type DataGridColumn,
  type DataGridLabels,
  type DataGridStatus,
} from "@numo9/ui";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useFormatMessage } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

import { contactsApi, firstError, type ContactRoleKey, type ContactSummary } from "./api";
import { lm } from "./listMessages";
import { ROLE_LABEL, ROLE_TITLE, ROLES } from "./roles";

type Tab = "all" | ContactRoleKey | "archived";

function useLabels(): DataGridLabels {
  const fm = useFormatMessage();
  return {
    grid: fm(lm.grid),
    search: fm(lm.search),
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
    resultCount: (shown, total) => fm(lm.results, { shown, total }),
    loading: fm(lm.loading),
  };
}

export function contactUrl(org: string, id: string): string {
  return `${orgModuleUrl(org, "contacts")}/${id}`;
}

export function ContactsScreen({ org, initialTab = "all" }: { org: string; initialTab?: Tab }) {
  const fm = useFormatMessage();
  const labels = useLabels();
  const [tab, setTab] = useState<Tab>(initialTab);
  const [rows, setRows] = useState<ContactSummary[]>([]);
  const [counts, setCounts] = useState<Partial<Record<ContactRoleKey, number>>>({});
  const [status, setStatus] = useState<DataGridStatus>("loading");
  const [attempt, setAttempt] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [notice, setNotice] = useState("");
  const [viewName, setViewName] = useState("");
  const store = useMemo(() => localSavedViewsStore(`numo9:contacts:${org}`), [org]);
  const views = useSavedViews(store);

  const load = useCallback(async () => {
    const result = await contactsApi.list(org, {
      role: tab === "all" || tab === "archived" ? undefined : tab,
      status: tab === "archived" ? "archived" : "active",
    });
    if (result.status === 200 && Array.isArray(result.body?.results)) {
      setRows(result.body.results);
      setCounts(result.body.role_counts ?? {});
      setStatus("ready");
    } else {
      setStatus("error");
    }
  }, [org, tab]);

  useEffect(() => {
    setStatus("loading");
    void load();
  }, [load, attempt]);

  const columns = useMemo<DataGridColumn<ContactSummary>[]>(
    () => [
      {
        id: "name",
        header: fm(lm.colName),
        accessor: (row) => row.display_name,
        sortable: true,
        hideable: false,
        cell: (row) => (
          <a
            href={contactUrl(org, row.id)}
            className="font-semibold text-fg underline"
            onClick={(event) => event.stopPropagation()}
          >
            {row.display_name}
          </a>
        ),
      },
      { id: "number", header: fm(lm.colNumber), accessor: (row) => row.number, sortable: true },
      {
        id: "roles",
        header: fm(lm.colRoles),
        accessor: (row) => row.roles.map((role) => fm(ROLE_LABEL[role])).join(", "),
        searchable: false,
      },
      { id: "person", header: fm(lm.colPerson), accessor: (row) => row.person },
      { id: "email", header: fm(lm.colEmail), accessor: (row) => row.email },
      { id: "phone", header: fm(lm.colPhone), accessor: (row) => row.phone, searchable: false },
      {
        id: "province",
        header: fm(lm.colProvince),
        accessor: (row) => row.province,
        sortable: true,
        width: 110,
      },
      {
        id: "currency",
        header: fm(lm.colCurrency),
        accessor: (row) => row.currency,
        width: 110,
        searchable: false,
      },
    ],
    [fm, org],
  );

  const bulk = async (action: "archive" | "restore") => {
    const ids = [...selected];
    const results = await Promise.all(
      ids.map((id) =>
        action === "archive" ? contactsApi.archive(org, id) : contactsApi.restore(org, id),
      ),
    );
    const failed = results.find((r) => r.status !== 200);
    const done = results.filter((r) => r.status === 200).length;
    setNotice(
      failed
        ? (firstError(failed.body) ?? fm(lm.actionFailed))
        : fm(action === "archive" ? lm.archivedCount : lm.restoredCount, { count: done }),
    );
    setSelected(new Set());
    await load();
  };

  const title =
    tab === "all"
      ? fm(lm.titleAll)
      : tab === "archived"
        ? fm(lm.titleArchived)
        : fm(ROLE_TITLE[tab]);

  const grid = (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-2">
        <Select
          aria-label={fm(lm.views)}
          value={views.activeId ?? "none"}
          onValueChange={(value) => {
            if (value !== "none") views.apply(value);
          }}
          options={[
            { value: "none", label: fm(lm.noView) },
            ...views.views.map((view) => ({ value: view.id, label: view.name })),
          ]}
        />
        <Input
          aria-label={fm(lm.viewName)}
          placeholder={fm(lm.viewName)}
          value={viewName}
          onChange={(event) => setViewName(event.target.value)}
          className="w-48"
        />
        <Button
          disabled={!viewName.trim()}
          onClick={() => {
            views.saveAs(viewName.trim());
            setViewName("");
          }}
        >
          {fm(lm.saveView)}
        </Button>
      </div>
      <DataGrid
        data={rows}
        columns={columns}
        getRowId={(row) => row.id}
        getRowLabel={(row) => row.display_name}
        labels={labels}
        status={status}
        view={views.view}
        onViewChange={views.setView}
        selectable
        selectedIds={selected}
        onSelectionChange={setSelected}
        onRowOpen={(row) => window.location.assign(contactUrl(org, row.id))}
        bulkActions={() =>
          tab === "archived" ? (
            <Button size="sm" onClick={() => void bulk("restore")}>
              {fm(lm.restoreSelected)}
            </Button>
          ) : (
            <Button size="sm" variant="danger" onClick={() => void bulk("archive")}>
              {fm(lm.archiveSelected)}
            </Button>
          )
        }
        emptyState={
          <EmptyState
            title={fm(lm.empty)}
            body={fm(lm.emptyBody)}
            actions={[
              <a
                key="new"
                href={`${orgModuleUrl(org, "contacts")}/new`}
                className="font-semibold underline"
              >
                {fm(lm.newContact)}
              </a>,
            ]}
          />
        }
        noResultsState={<EmptyState title={fm(lm.noResults)} compact />}
        errorState={
          <ErrorState
            title={fm(lm.failed)}
            retryLabel={fm(lm.retry)}
            onRetry={() => setAttempt((n) => n + 1)}
            headingLevel={2}
          />
        }
      />
    </div>
  );

  const tabs: Tab[] = ["all", ...ROLES, "archived"];
  const tabLabel = (value: Tab) =>
    value === "all"
      ? fm(lm.tabAll)
      : value === "archived"
        ? fm(lm.tabArchived)
        : fm(ROLE_TITLE[value]);

  return (
    <div className="flex flex-col gap-4" data-contacts-screen="">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <h1 className="text-2xl font-bold text-fg">{title}</h1>
        <a
          href={`${orgModuleUrl(org, "contacts")}/new`}
          className="inline-flex min-h-touch-target items-center rounded-md bg-surface-accent px-4 text-sm font-semibold text-fg-on-accent hover:bg-surface-accent-hover"
        >
          {fm(lm.newContact)}
        </a>
      </header>
      <p role="status" className="min-h-5 text-sm text-fg-muted">
        {notice}
      </p>
      <Tabs
        label={fm(lm.tabs)}
        value={tab}
        onValueChange={(value) => {
          setTab(value as Tab);
          setSelected(new Set());
          setNotice("");
        }}
        items={tabs.map((value) => ({
          value,
          label: tabLabel(value),
          count: value !== "all" && value !== "archived" ? counts[value] : undefined,
          content: value === tab ? grid : null,
        }))}
      />
    </div>
  );
}
