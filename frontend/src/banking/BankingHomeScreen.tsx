"use client";

/**
 * Banking home (F-01-T08, wireframe 38): one card per bank, credit card, loan, cash or clearing
 * account — type icon, name, institution and currency, the **ledger balance** (always the
 * ledger, a liability reads "owed"), the optional statement balance and its date, the
 * "Not reconciled — optional" chip and the last activity. Skeleton cards while balances load; an
 * error with **Try again** that blocks nothing else; an empty state that explains no feed is
 * needed; archived accounts under "Archived" (hidden from pickers, kept in reports) with Restore.
 */
import {
  Badge,
  Button,
  EmptyState,
  ErrorState,
  Skeleton,
  formatDate,
  formatMoney,
  type AppLocale,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { useFormatMessage } from "@/i18n";

import { bankingApi, type BankAccount, type BankAccountType } from "./api";
import { m, typeLabels } from "./messages";

const TIME_ZONE = "America/Toronto";

export interface BankingHomeProps {
  org: string;
  /** Opens the add-account side-sheet (F-01-T09). */
  onAddAccount?: () => void;
  /** Increment to reload the cards (after an account is added). */
  refreshKey?: number;
  /** Rendered above the cards (the no-bank prompt, F-01-T12). */
  banner?: ReactNode;
}

export function BankingHomeScreen({ org, onAddAccount, refreshKey = 0, banner }: BankingHomeProps) {
  const fm = useFormatMessage();
  const [accounts, setAccounts] = useState<BankAccount[] | null>(null);
  const [archived, setArchived] = useState<BankAccount[]>([]);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [showArchived, setShowArchived] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    void bankingApi.accounts(org, "all").then((result) => {
      if (cancelled) return;
      if (result.status === 200 && Array.isArray(result.body?.results)) {
        setAccounts(result.body.results.filter((a) => !a.archived_at));
        setArchived(result.body.results.filter((a) => a.archived_at));
      } else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [org, attempt, refreshKey]);

  const restore = useCallback(
    async (account: BankAccount) => {
      const result = await bankingApi.restore(org, account.id);
      if (result.status === 200) {
        setStatus(fm(m.restored, { name: account.display_name }));
        setAttempt((n) => n + 1);
      }
    },
    [org, fm],
  );

  const header = (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex max-w-3xl flex-col gap-1">
        <h1 className="text-2xl font-bold text-fg">{fm(m.title)}</h1>
        <p className="text-sm text-fg-muted">{fm(m.intro)}</p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" onClick={onAddAccount}>
          {fm(m.addAccount)}
        </Button>
      </div>
    </div>
  );

  if (failed) {
    return (
      <div className="flex flex-col gap-6">
        {header}
        {banner}
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
  if (accounts === null) {
    return (
      <div className="flex flex-col gap-6" aria-busy="true">
        {header}
        <p className="sr-only">{fm(m.loading)}</p>
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-hidden="true">
          {[0, 1, 2].map((n) => (
            <li key={n} className="rounded-lg border border-border p-4" data-skeleton-card="">
              <Skeleton width="60%" />
              <div className="mt-4">
                <Skeleton width="40%" height={28} />
              </div>
              <div className="mt-3">
                <Skeleton width="80%" />
              </div>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6" data-banking-home="">
      {header}
      {banner}
      <p role="status" className="sr-only">
        {status}
      </p>
      {accounts.length === 0 ? (
        <EmptyState
          title={fm(m.emptyTitle)}
          body={fm(m.emptyBody)}
          headingLevel={2}
          actions={[
            <Button key="add" variant="primary" onClick={onAddAccount}>
              {fm(m.addAccount)}
            </Button>,
          ]}
        />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {accounts.map((account) => (
            <li key={account.id}>
              <AccountCard org={org} account={account} />
            </li>
          ))}
        </ul>
      )}
      {archived.length > 0 ? (
        <section aria-labelledby="banking-archived" className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3">
            <h2 id="banking-archived" className="text-lg font-semibold text-fg">
              {fm(m.archivedHeading, { count: archived.length })}
            </h2>
            <Button
              variant="ghost"
              onClick={() => setShowArchived((v) => !v)}
              aria-expanded={showArchived}
            >
              {fm(m.showArchived)}
            </Button>
          </div>
          <p className="text-sm text-fg-muted">{fm(m.archivedNote)}</p>
          {showArchived ? (
            <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" data-archived="">
              {archived.map((account) => (
                <li key={account.id} className="opacity-70">
                  <AccountCard org={org} account={account} />
                  <div className="mt-2">
                    <Button variant="secondary" onClick={() => void restore(account)}>
                      {fm(m.restore)}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

/** Ledger balance as shown: a liability's credit balance reads "$1,200.00 owed". */
export function balanceLabel(
  account: Pick<BankAccount, "ledger_balance" | "is_liability" | "currency">,
  locale: AppLocale,
  owed: (amount: string) => string,
): string {
  const value = account.ledger_balance;
  if (account.is_liability) {
    const flipped = value.startsWith("-") ? value.slice(1) : value === "0.00" ? value : `-${value}`;
    return owed(formatMoney(flipped, { locale, currency: account.currency }));
  }
  return formatMoney(value, { locale, currency: account.currency });
}

function AccountCard({ org, account }: { org: string; account: BankAccount }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const negative = !account.is_liability && account.ledger_balance.startsWith("-");
  const subtitle = [
    fm(typeLabels[account.type]),
    account.institution,
    account.currency,
    account.masked_number,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <article
      aria-labelledby={`bank-${account.id}`}
      className="flex h-full flex-col gap-3 rounded-lg border border-border bg-surface p-4"
      data-bank-card={account.type}
    >
      <div className="flex items-start gap-3">
        <TypeIcon type={account.type} />
        <div className="min-w-0 flex-1">
          <h2 id={`bank-${account.id}`} className="truncate text-base font-semibold text-fg">
            <Link href={`/o/${org}/banking/${account.id}`} className="hover:underline">
              {account.display_name}
            </Link>
          </h2>
          <p className="truncate text-xs text-fg-muted">{subtitle}</p>
        </div>
      </div>
      <div>
        <p className="text-xs text-fg-muted">{fm(m.ledgerBalance)}</p>
        <p
          className={`text-2xl font-bold tabular-nums ${negative ? "text-fg-danger" : "text-fg"}`}
          data-ledger-balance=""
        >
          {balanceLabel(account, locale, (amount) => fm(m.owed, { amount }))}
        </p>
        <p className="text-xs text-fg-muted">
          {account.statement_balance !== null && account.statement_balance_date
            ? fm(m.statementBalance, {
                amount: formatMoney(account.statement_balance, {
                  locale,
                  currency: account.currency,
                }),
                date: formatDate(account.statement_balance_date, { locale, timeZone: TIME_ZONE }),
              })
            : fm(m.noStatement)}
        </p>
      </div>
      <div className="mt-auto flex flex-wrap items-center justify-between gap-2">
        <Badge tone={account.is_reconciled_tracking ? "info" : "neutral"}>
          {fm(account.is_reconciled_tracking ? m.reconcileTracked : m.reconcileOptional)}
        </Badge>
        <span className="text-xs text-fg-muted">
          {account.last_activity
            ? fm(m.lastActivity, {
                date: formatDate(account.last_activity, { locale, timeZone: TIME_ZONE }),
              })
            : fm(m.noActivity)}
        </span>
      </div>
    </article>
  );
}

const ICON_PATHS: Record<"bank" | "card" | "cash", string> = {
  bank: "M3 10h18M5 10v7m4-7v7m6-7v7m4-7v7M3 20h18M12 3l9 5H3z",
  card: "M3 6h18v12H3zM3 10h18M7 15h4",
  cash: "M3 7h18v10H3zM12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5",
};

function iconFor(type: BankAccountType): keyof typeof ICON_PATHS {
  if (type === "credit_card" || type === "line_of_credit") return "card";
  if (type === "cash") return "cash";
  return "bank";
}

function TypeIcon({ type }: { type: BankAccountType }) {
  return (
    <span
      aria-hidden="true"
      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-surface-muted"
      data-type-icon={iconFor(type)}
    >
      <svg
        viewBox="0 0 24 24"
        width="20"
        height="20"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      >
        <path d={ICON_PATHS[iconFor(type)]} strokeLinejoin="round" strokeLinecap="round" />
      </svg>
    </span>
  );
}
