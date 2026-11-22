"use client";

/**
 * Bank account detail (F-01-T11, wireframe 40): the account's ledger balance and optional
 * statement balance, Spend money / Receive money, and every transaction that moved it with the
 * **running balance** after it (computed over the whole history on the server, so filtered rows
 * keep true balances; with no filter the last row's balance is the ledger balance). Filters: date
 * range, contact, amount range, status. The grid's column chooser hides columns; Export CSV /
 * Excel downloads the filtered rows.
 */
import {
  Badge,
  Button,
  DataGrid,
  EmptyState,
  ErrorState,
  Input,
  formatDate,
  formatMoney,
  type AppLocale,
  type DataGridColumn,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useId, useMemo, useState, type FormEvent, type ReactNode } from "react";

import { useGridLabels } from "@/directory/DirectoryScreen";
import { useFormatMessage } from "@/i18n";

import {
  registerApi,
  registerUrl,
  type BankAccount,
  type RegisterFilters,
  type RegisterRow,
} from "./api";
import { spendUrl } from "./BankingHome";
import { balanceLabel } from "./BankingHomeScreen";
import { m, reg, typeLabels } from "./messages";

const TIME_ZONE = "America/Toronto";

export function BankAccountDetail({ org, account: id }: { org: string; account: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [account, setAccount] = useState<BankAccount | null>(null);
  const [rows, setRows] = useState<RegisterRow[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [filters, setFilters] = useState<RegisterFilters>({});
  const [draft, setDraft] = useState<RegisterFilters>({});
  const [attempt, setAttempt] = useState(0);
  const [contacts, setContacts] = useState<{ id: string; name: string }[]>([]);
  const baseLabels = useGridLabels(fm);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    void registerApi.get(org, id, filters).then((result) => {
      if (cancelled) return;
      if (result.status === 200 && Array.isArray(result.body?.results)) {
        setAccount(result.body.account);
        setRows(result.body.results);
        setFailed(false);
        if (Object.keys(filters).length === 0) {
          const seen = new Map<string, string>();
          for (const row of result.body.results) {
            if (row.contact) seen.set(row.contact.id, row.contact.name);
          }
          setContacts([...seen].map(([value, name]) => ({ id: value, name })));
        }
      } else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [org, id, filters, attempt]);

  const currency = account?.currency ?? "CAD";
  const columns = useMemo<DataGridColumn<RegisterRow>[]>(() => {
    const money = (value: string | null) =>
      value === null ? "" : formatMoney(value, { locale, currency });
    return [
      {
        id: "date",
        header: fm(reg.colDate),
        accessor: (row) => row.date,
        cell: (row) => formatDate(row.date, { locale, timeZone: TIME_ZONE }),
        width: 120,
        hideable: false,
      },
      {
        id: "journal",
        header: fm(reg.colJournal),
        accessor: (row) => row.journal.number,
        cell: (row) => (
          <Link href={`/o/${org}/accounting/journals/${row.journal.id}`} className="underline">
            {row.journal.number}
          </Link>
        ),
        width: 120,
      },
      {
        id: "contact",
        header: fm(reg.colContact),
        accessor: (row) => row.contact?.name ?? "",
      },
      { id: "description", header: fm(reg.colDescription), accessor: (row) => row.description },
      { id: "reference", header: fm(reg.colReference), accessor: (row) => row.reference },
      {
        id: "received",
        header: fm(reg.colReceived),
        accessor: (row) => row.received ?? "",
        cell: (row) => money(row.received),
        align: "end",
        width: 130,
      },
      {
        id: "spent",
        header: fm(reg.colSpent),
        accessor: (row) => row.spent ?? "",
        cell: (row) => money(row.spent),
        align: "end",
        width: 130,
      },
      {
        id: "balance",
        header: fm(reg.colBalance),
        accessor: (row) => row.balance,
        cell: (row) => (
          <span className={row.balance.startsWith("-") ? "text-fg-danger" : undefined}>
            {money(row.balance)}
          </span>
        ),
        align: "end",
        width: 150,
        hideable: false,
      },
      {
        id: "status",
        header: fm(reg.colStatus),
        accessor: (row) => (row.voided ? "voided" : row.status),
        cell: (row) =>
          row.voided ? (
            <Badge tone="warning">{fm(reg.statusVoided)}</Badge>
          ) : row.status === "reversed" ? (
            <Badge tone="neutral">{fm(reg.statusReversed)}</Badge>
          ) : (
            <Badge tone="success">{fm(reg.statusPosted)}</Badge>
          ),
        width: 110,
      },
    ];
  }, [fm, locale, org, currency]);

  const labels = useMemo(
    () => ({
      ...baseLabels,
      grid: fm(reg.grid),
      loading: fm(reg.loading),
      resultCount: (shown: number, total: number) => fm(reg.results, { shown, total }),
    }),
    [baseLabels, fm],
  );

  if (failed) {
    return (
      <ErrorState
        title={fm(reg.loadFailed)}
        body={fm(m.loadFailedBody)}
        retryLabel={fm(m.retry)}
        onRetry={() => setAttempt((n) => n + 1)}
        headingLevel={2}
      />
    );
  }

  const apply = (event: FormEvent) => {
    event.preventDefault();
    setFilters(Object.fromEntries(Object.entries(draft).filter(([, v]) => Boolean(v))));
  };
  const filtered = Object.keys(filters).length > 0;
  const set = (key: keyof RegisterFilters) => (value: string) =>
    setDraft((current) => ({ ...current, [key]: value }));

  return (
    <div className="flex flex-col gap-6" data-bank-detail="">
      <nav aria-label={fm(reg.back)} className="text-sm">
        <Link href={`/o/${org}/banking`} className="underline">
          {fm(reg.back)}
        </Link>
      </nav>
      {account ? (
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-2xl font-bold text-fg">{account.display_name}</h1>
            <p className="text-sm text-fg-muted">
              {[
                fm(typeLabels[account.type]),
                account.institution,
                account.currency,
                account.masked_number,
                `${account.ledger_account.code} · ${account.ledger_account.name}`,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <div className="flex flex-col items-end gap-1">
            <p className="text-xs text-fg-muted">{fm(m.ledgerBalance)}</p>
            <p className="text-2xl font-bold tabular-nums" data-ledger-balance="">
              {balanceLabel(account, locale, (amount) => fm(m.owed, { amount }))}
            </p>
            <p className="text-xs text-fg-muted">
              {account.statement_balance !== null && account.statement_balance_date
                ? fm(m.statementBalance, {
                    amount: formatMoney(account.statement_balance, {
                      locale,
                      currency: account.currency,
                    }),
                    date: formatDate(account.statement_balance_date, {
                      locale,
                      timeZone: TIME_ZONE,
                    }),
                  })
                : fm(reg.statementNone)}
            </p>
          </div>
        </header>
      ) : null}
      <div className="flex flex-wrap gap-3">
        <Link
          href={spendUrl(org, id)}
          className="rounded-md bg-surface-accent px-4 py-2 text-sm font-semibold text-fg"
        >
          {fm(m.spendMoney)}
        </Link>
        <Link
          href={`/o/${org}/banking/receive?account=${encodeURIComponent(id)}`}
          className="rounded-md border border-border px-4 py-2 text-sm font-semibold text-fg"
        >
          {fm(m.receiveMoney)}
        </Link>
      </div>
      <form
        aria-label={fm(reg.filters)}
        className="flex flex-wrap items-end gap-3"
        onSubmit={apply}
        data-register-filters=""
      >
        <FilterField id={`${ids}-from`} label={fm(reg.from)}>
          <Input
            id={`${ids}-from`}
            type="date"
            value={draft.date_from ?? ""}
            onChange={(e) => set("date_from")(e.target.value)}
          />
        </FilterField>
        <FilterField id={`${ids}-to`} label={fm(reg.to)}>
          <Input
            id={`${ids}-to`}
            type="date"
            value={draft.date_to ?? ""}
            onChange={(e) => set("date_to")(e.target.value)}
          />
        </FilterField>
        <FilterField id={`${ids}-contact`} label={fm(reg.contact)}>
          <select
            id={`${ids}-contact`}
            value={draft.contact ?? ""}
            onChange={(e) => set("contact")(e.target.value)}
            className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-fg"
          >
            <option value="">{fm(reg.anyContact)}</option>
            {contacts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </FilterField>
        <FilterField id={`${ids}-min`} label={fm(reg.amountMin)}>
          <Input
            id={`${ids}-min`}
            inputMode="decimal"
            value={draft.amount_min ?? ""}
            onChange={(e) => set("amount_min")(e.target.value)}
            className="w-28"
          />
        </FilterField>
        <FilterField id={`${ids}-max`} label={fm(reg.amountMax)}>
          <Input
            id={`${ids}-max`}
            inputMode="decimal"
            value={draft.amount_max ?? ""}
            onChange={(e) => set("amount_max")(e.target.value)}
            className="w-28"
          />
        </FilterField>
        <FilterField id={`${ids}-status`} label={fm(reg.status)}>
          <select
            id={`${ids}-status`}
            value={draft.status ?? ""}
            onChange={(e) => set("status")(e.target.value)}
            className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-fg"
          >
            <option value="">{fm(reg.anyStatus)}</option>
            <option value="posted">{fm(reg.statusPosted)}</option>
            <option value="reversed">{fm(reg.statusReversed)}</option>
          </select>
        </FilterField>
        <Button type="submit" variant="secondary">
          {fm(reg.apply)}
        </Button>
        {filtered ? (
          <Button
            variant="ghost"
            onClick={() => {
              setDraft({});
              setFilters({});
            }}
          >
            {fm(reg.clear)}
          </Button>
        ) : null}
      </form>
      <DataGrid
        data={rows ?? []}
        columns={columns}
        getRowId={(row) => row.id}
        getRowLabel={(row) => `${row.date} ${row.description}`}
        labels={labels}
        status={rows === null ? "loading" : "ready"}
        emptyState={
          filtered ? (
            <EmptyState title={fm(reg.noMatch)} headingLevel={2} compact />
          ) : (
            <EmptyState title={fm(reg.empty)} body={fm(reg.emptyBody)} headingLevel={2} />
          )
        }
        toolbar={
          <div className="flex gap-2">
            <a
              href={registerUrl(org, id, filters, "csv")}
              download
              className="rounded-md border border-border px-3 py-2 text-sm text-fg"
            >
              {fm(reg.exportCsv)}
            </a>
            <a
              href={registerUrl(org, id, filters, "xlsx")}
              download
              className="rounded-md border border-border px-3 py-2 text-sm text-fg"
            >
              {fm(reg.exportXlsx)}
            </a>
          </div>
        }
        height={560}
      />
    </div>
  );
}

function FilterField({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-fg-muted">
        {label}
      </label>
      {children}
    </div>
  );
}
