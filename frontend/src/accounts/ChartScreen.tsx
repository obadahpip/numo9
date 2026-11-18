"use client";

/**
 * Chart of accounts (C-01-T11): the tree table — children indented under their parents, expand and
 * collapse, type tabs (All, Assets … Expenses, Archived), search, inline code edit with the
 * server's conflict message, row selection with bulk archive / restore (each account's outcome
 * reported). A name opens the account drawer (C-01-T12).
 */
import {
  Badge,
  Button,
  ChevronDownIcon,
  DataGrid,
  EmptyState,
  ErrorState,
  formatMoney,
  Input,
  Tabs,
  type AppLocale,
  type DataGridColumn,
  type DataGridLabels,
  type DataGridStatus,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

import { useFormatMessage } from "@/i18n";

import { AccountDrawer } from "./AccountDrawer";
import { accountsApi, refusal, type Account, type AccountType } from "./api";
import { m } from "./messages";

type Tab = "all" | AccountType | "archived";
const TYPE_TABS: AccountType[] = ["asset", "liability", "equity", "revenue", "expense"];
const INDENT = ["", "ps-6", "ps-12", "ps-18"] as const;

function useLabels(): DataGridLabels {
  const fm = useFormatMessage();
  return {
    grid: fm(m.grid),
    search: fm(m.search),
    columns: fm(m.columns),
    density: fm(m.density),
    comfortable: fm(m.comfortable),
    compact: fm(m.compact),
    filterAll: fm(m.all),
    filterChip: (column, value) => fm(m.chip, { column, value }),
    clearFilters: fm(m.clear),
    selectAll: fm(m.selectAll),
    selectRow: (row) => fm(m.selectRow, { row }),
    selectedCount: (count) => fm(m.selected, { count }),
    clearSelection: fm(m.clearSelection),
    resultCount: (shown, total) => fm(m.results, { shown, total }),
    loading: fm(m.loading),
  };
}

/** Rows of the tab, without the descendants of collapsed accounts (server order = tree order). */
function visibleRows(rows: Account[], tab: Tab, collapsed: ReadonlySet<string>): Account[] {
  const parent = new Map(rows.map((row) => [row.id, row.parent]));
  const hidden = (row: Account) => {
    for (let up = row.parent; up; up = parent.get(up) ?? null) {
      if (collapsed.has(up)) return true;
    }
    return false;
  };
  return rows.filter((row) => {
    if (tab === "archived" ? row.status !== "archived" : row.status !== "active") return false;
    if (tab !== "all" && tab !== "archived" && row.type !== tab) return false;
    return !hidden(row);
  });
}

/** Tree order: each account followed by its sub-accounts, codes in order at every level. */
function treeOrder(rows: Account[]): Account[] {
  const children = new Map<string | null, Account[]>();
  for (const row of rows) {
    const known = row.parent && rows.some((r) => r.id === row.parent) ? row.parent : null;
    children.set(known, [...(children.get(known) ?? []), row]);
  }
  const out: Account[] = [];
  const walk = (key: string | null) => {
    for (const row of children.get(key) ?? []) {
      out.push(row);
      walk(row.id);
    }
  };
  walk(null);
  return out;
}

function CodeCell({
  org,
  account,
  onRenumbered,
}: {
  org: string;
  account: Account;
  onRenumbered: (account: Account, message: string) => void;
}) {
  const fm = useFormatMessage();
  const [editing, setEditing] = useState(false);
  const [code, setCode] = useState(account.code);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  if (!editing) {
    return (
      <button
        type="button"
        className="rounded-sm font-mono text-sm underline decoration-dotted"
        aria-label={fm(m.renumberOpen, { code: account.code })}
        onClick={(event) => {
          event.stopPropagation();
          setEditing(true);
        }}
      >
        {account.code}
      </button>
    );
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (code.trim() === account.code) {
      setEditing(false);
      return;
    }
    setBusy(true);
    const result = await accountsApi.renumber(org, account.id, code.trim());
    setBusy(false);
    if (result.status === 200) {
      setEditing(false);
      setError("");
      onRenumbered(result.body, fm(m.renumbered, { name: account.name, code: result.body.code }));
    } else {
      setError(refusal(result) ?? fm(m.saveFailed));
    }
  };
  const errorId = `code-error-${account.id}`;
  return (
    <form
      onSubmit={(event) => void submit(event)}
      onClick={(event) => event.stopPropagation()}
      onKeyDown={(event) => {
        event.stopPropagation();
        if (event.key === "Escape") {
          setEditing(false);
          setCode(account.code);
          setError("");
        }
      }}
      className="flex flex-col gap-1"
    >
      <Input
        autoFocus
        value={code}
        disabled={busy}
        onChange={(event) => setCode(event.target.value)}
        aria-label={fm(m.newCode, { name: account.name })}
        aria-describedby={error ? errorId : undefined}
        invalid={Boolean(error)}
        className="w-24 font-mono"
      />
      {error ? (
        <span id={errorId} role="alert" className="max-w-64 text-xs text-fg-danger">
          {error}
        </span>
      ) : null}
    </form>
  );
}

export function ChartScreen({ org }: { org: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const labels = useLabels();
  const [rows, setRows] = useState<Account[]>([]);
  const [status, setStatus] = useState<DataGridStatus>("loading");
  const [attempt, setAttempt] = useState(0);
  const [tab, setTab] = useState<Tab>("all");
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<Account | null>(null);
  const [notice, setNotice] = useState("");
  const [failures, setFailures] = useState<string[]>([]);

  const load = useCallback(async () => {
    const result = await accountsApi.list(org, "all");
    if (result.status === 200 && Array.isArray(result.body?.results)) {
      setRows(treeOrder(result.body.results));
      setStatus("ready");
    } else {
      setStatus("error");
    }
  }, [org]);

  useEffect(() => {
    setStatus("loading");
    void load();
  }, [load, attempt]);

  const replace = useCallback((account: Account) => {
    setRows((current) => current.map((row) => (row.id === account.id ? account : row)));
  }, []);

  const visible = useMemo(() => visibleRows(rows, tab, collapsed), [rows, tab, collapsed]);

  const columns = useMemo<DataGridColumn<Account>[]>(
    () => [
      {
        id: "code",
        header: fm(m.colCode),
        accessor: (row) => row.code,
        width: 130,
        hideable: false,
        cell: (row) => (
          <CodeCell
            org={org}
            account={row}
            onRenumbered={(account, message) => {
              replace(account);
              setNotice(message);
            }}
          />
        ),
      },
      {
        id: "name",
        header: fm(m.colName),
        accessor: (row) => row.name,
        hideable: false,
        cell: (row) => (
          <span className={`flex items-center gap-2 ${INDENT[Math.min(row.depth - 1, 3)] ?? ""}`}>
            {row.has_children ? (
              <button
                type="button"
                className="min-h-6 min-w-6 rounded-sm text-fg-muted"
                aria-expanded={!collapsed.has(row.id)}
                aria-label={fm(collapsed.has(row.id) ? m.expand : m.collapse, { name: row.name })}
                onClick={(event) => {
                  event.stopPropagation();
                  setCollapsed((current) => {
                    const next = new Set(current);
                    if (next.has(row.id)) next.delete(row.id);
                    else next.add(row.id);
                    return next;
                  });
                }}
              >
                <span
                  aria-hidden="true"
                  className={`inline-flex ${collapsed.has(row.id) ? "-rotate-90" : ""}`}
                >
                  <ChevronDownIcon />
                </span>
              </button>
            ) : (
              <span className="inline-block min-w-6" aria-hidden="true" />
            )}
            <button
              type="button"
              className="text-start font-semibold text-fg underline"
              onClick={(event) => {
                event.stopPropagation();
                setOpen(row);
              }}
            >
              {row.name}
            </button>
            {row.system_role ? (
              <Badge tone="inverse">{fm(m.system, { role: row.system_role_label })}</Badge>
            ) : null}
          </span>
        ),
      },
      {
        id: "type",
        header: fm(m.colType),
        accessor: (row) => row.subtype_label,
        searchable: false,
        width: 200,
      },
      {
        id: "gifi",
        header: fm(m.colGifi),
        accessor: (row) => row.gifi?.code ?? "",
        width: 90,
      },
      {
        id: "balance",
        header: fm(m.colBalance),
        accessor: (row) => row.balance.accounting,
        align: "end",
        searchable: false,
        width: 150,
        cell: (row) => formatMoney(row.balance.accounting, { locale }),
      },
    ],
    [collapsed, fm, locale, org, replace],
  );

  const runBulk = async (action: "archive" | "restore") => {
    const result = await accountsApi.bulk(org, [...selected], action);
    if (result.status !== 200) {
      setNotice(refusal(result) ?? fm(m.saveFailed));
      return;
    }
    setNotice(fm(m.bulkDone, { done: result.body.done, failed: result.body.failed }));
    setFailures(
      result.body.results
        .filter((outcome) => !outcome.ok)
        .map((outcome) =>
          fm(m.bulkFailedLine, { code: outcome.code ?? "", reason: outcome.detail ?? "" }),
        ),
    );
    setSelected(new Set());
    await load();
  };

  const grid = (
    <DataGrid
      data={visible}
      columns={columns}
      getRowId={(row) => row.id}
      getRowLabel={(row) => `${row.code} ${row.name}`}
      labels={labels}
      status={status}
      selectable
      selectedIds={selected}
      onSelectionChange={setSelected}
      onRowOpen={(row) => setOpen(row)}
      bulkActions={() =>
        tab === "archived" ? (
          <Button size="sm" onClick={() => void runBulk("restore")}>
            {fm(m.restoreSelected)}
          </Button>
        ) : (
          <Button size="sm" variant="danger" onClick={() => void runBulk("archive")}>
            {fm(m.archiveSelected)}
          </Button>
        )
      }
      emptyState={<EmptyState title={fm(m.empty)} body={fm(m.emptyBody)} />}
      noResultsState={<EmptyState title={fm(m.noResults)} compact />}
      errorState={
        <ErrorState
          title={fm(m.failed)}
          retryLabel={fm(m.retry)}
          onRetry={() => setAttempt((n) => n + 1)}
          headingLevel={2}
        />
      }
    />
  );

  const tabLabel: Record<Tab, string> = {
    all: fm(m.tabAll),
    asset: fm(m.tabAsset),
    liability: fm(m.tabLiability),
    equity: fm(m.tabEquity),
    revenue: fm(m.tabRevenue),
    expense: fm(m.tabExpense),
    archived: fm(m.tabArchived),
  };
  const tabs: Tab[] = ["all", ...TYPE_TABS, "archived"];

  return (
    <div className="flex flex-col gap-4" data-chart-screen="">
      <div>
        <h1 className="text-2xl font-bold text-fg">{fm(m.title)}</h1>
        <p className="max-w-prose text-sm text-fg-muted">{fm(m.intro)}</p>
      </div>
      <p role="status" className="min-h-5 text-sm text-fg-muted">
        {notice}
      </p>
      {failures.length > 0 ? (
        <ul role="alert" className="text-sm text-fg-danger">
          {failures.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}
      <Tabs
        label={fm(m.tabs)}
        value={tab}
        onValueChange={(value) => {
          setTab(value as Tab);
          setSelected(new Set());
        }}
        items={tabs.map((value) => ({
          value,
          label: tabLabel[value],
          count:
            status === "ready"
              ? rows.filter((row) =>
                  value === "archived"
                    ? row.status === "archived"
                    : row.status === "active" && (value === "all" || row.type === value),
                ).length
              : undefined,
          content: value === tab ? grid : null,
        }))}
      />
      {open ? (
        <AccountDrawer
          org={org}
          account={open}
          onClose={() => setOpen(null)}
          onChange={(account) => {
            replace(account);
            setOpen(account);
          }}
        />
      ) : null}
    </div>
  );
}
