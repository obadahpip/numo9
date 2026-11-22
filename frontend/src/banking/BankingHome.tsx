"use client";

/**
 * The banking page (F-01): the home screen, the add-account side-sheet (T09) and the notice
 * after adding an account — "… is ready." with **Record a transaction** (spend money from it).
 */
import { Button } from "@numo9/ui";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { AddAccountSheet } from "./AddAccountSheet";
import type { BankAccount } from "./api";
import { BankingHomeScreen } from "./BankingHomeScreen";
import { sheet } from "./messages";
import { NoBankPrompt } from "./NoBankPrompt";

/** The spend-money form for an account (F-01-T10). */
export function spendUrl(org: string, account: string): string {
  return `/o/${org}/banking/spend?account=${encodeURIComponent(account)}`;
}

export function BankingHome({ org }: { org: string }) {
  const fm = useFormatMessage();
  const [adding, setAdding] = useState(false);
  const [created, setCreated] = useState<BankAccount | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [count, setCount] = useState<number | undefined>(undefined);

  // `/o/:org/banking?add=1` (the dashboard prompt's button) opens the add-account sheet.
  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("add") === "1") setAdding(true);
  }, []);

  const notice = created ? (
    <div
      role="status"
      className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface-success-subtle p-4"
      data-created-notice=""
    >
      <p className="text-sm font-semibold text-fg">
        {fm(sheet.ready, { name: created.display_name })}
      </p>
      <div className="flex items-center gap-2">
        <Link
          href={spendUrl(org, created.id)}
          className="text-sm font-semibold text-fg underline underline-offset-2"
        >
          {fm(sheet.recordTransaction)}
        </Link>
        <Button variant="ghost" size="sm" onClick={() => setCreated(null)}>
          {fm(sheet.dismiss)}
        </Button>
      </div>
    </div>
  ) : null;

  return (
    <>
      <BankingHomeScreen
        org={org}
        onAddAccount={() => setAdding(true)}
        refreshKey={refresh}
        onLoaded={setCount}
        banner={
          <>
            {notice}
            {count === 0 ? (
              <NoBankPrompt org={org} count={0} onAdd={() => setAdding(true)} />
            ) : null}
          </>
        }
      />
      <AddAccountSheet
        org={org}
        open={adding}
        onOpenChange={setAdding}
        onCreated={(account) => {
          setCreated(account);
          setRefresh((n) => n + 1);
        }}
      />
    </>
  );
}
