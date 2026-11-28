"use client";

/**
 * Banking settings — the negative-balance policy (F-07-T08): for each account type that holds
 * money (Chequing, Savings, Cash / petty cash, Clearing), what happens when a posting would take
 * it below zero, for people who aren't advisers and for advisers: Allow, Warn (a reason is
 * asked and kept) or Block. Each type says why its default is what it is. Saved rows apply to
 * the very next posting.
 */
import { Button, ErrorState, Skeleton } from "@numo9/ui";
import { useCallback, useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import {
  cashPolicyApi,
  type CashControlAction,
  type CashPolicy,
  type CashPolicyChange,
} from "./api";
import { cash } from "./cashControlMessages";

const ACTIONS: readonly CashControlAction[] = ["allow", "warn", "block"];

export function CashPolicySettings({ org }: { org: string }) {
  const fm = useFormatMessage();
  const ids = useId();
  const [rows, setRows] = useState<CashPolicy[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<"saved" | "failed" | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    void cashPolicyApi
      .get(org)
      .then((result) => {
        if (!live) return;
        if (result.status === 200) setRows(result.body.policies);
        else setFailed(true);
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [org, attempt]);

  const label = (action: CashControlAction) =>
    fm(
      action === "allow"
        ? cash.actionAllow
        : action === "warn"
          ? cash.actionWarn
          : cash.actionBlock,
    );

  const change = useCallback(
    (type: string, level: "standard" | "adviser", action: CashControlAction) => {
      setStatus(null);
      setRows((current) =>
        (current ?? []).map((row) =>
          row.account_type === type ? { ...row, [level]: action } : row,
        ),
      );
    },
    [],
  );

  const save = async () => {
    if (!rows) return;
    setBusy(true);
    const body: CashPolicyChange[] = rows.map(({ account_type, standard, adviser }) => ({
      account_type,
      standard,
      adviser,
    }));
    const result = await cashPolicyApi.save(org, body).catch(() => null);
    setBusy(false);
    if (result?.status === 200) {
      setRows(result.body.policies);
      setStatus("saved");
    } else {
      setStatus("failed");
    }
  };

  if (failed)
    return (
      <ErrorState
        title={fm(cash.loadFailed)}
        retryLabel={fm(cash.retry)}
        onRetry={() => {
          setFailed(false);
          setAttempt((n) => n + 1);
        }}
      />
    );

  return (
    <div className="flex max-w-5xl flex-col gap-6 p-4">
      <h1 className="text-2xl font-bold text-fg">{fm(cash.settingsTitle)}</h1>
      <section aria-labelledby={`${ids}-policy`} className="flex flex-col gap-3">
        <h2 id={`${ids}-policy`} className="text-lg font-semibold text-fg">
          {fm(cash.policyHeading)}
        </h2>
        <p className="max-w-3xl text-sm text-fg-muted">{fm(cash.policyIntro)}</p>
        {rows === null ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <table className="w-full border-collapse text-sm" data-cash-policies="">
            <thead>
              <tr className="border-b border-border text-start">
                <th scope="col" className="py-2 pe-4 text-start font-semibold">
                  {fm(cash.colType)}
                </th>
                <th scope="col" className="py-2 pe-4 text-start font-semibold">
                  {fm(cash.colStandard)}
                </th>
                <th scope="col" className="py-2 text-start font-semibold">
                  {fm(cash.colAdviser)}
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.account_type}
                  className="border-b border-border align-top"
                  data-policy={row.account_type}
                >
                  <th scope="row" className="py-3 pe-4 text-start font-normal">
                    <span className="font-semibold text-fg">{row.label}</span>
                    <p className="mt-1 max-w-md text-fg-muted">{row.explanation}</p>
                    <p className="mt-1 text-xs text-fg-muted">
                      {fm(cash.defaultIs, {
                        standard: label(row.default.standard),
                        adviser: label(row.default.adviser),
                      })}
                    </p>
                  </th>
                  {(["standard", "adviser"] as const).map((level) => (
                    <td key={level} className="py-3 pe-4">
                      <select
                        aria-label={fm(level === "standard" ? cash.standardFor : cash.adviserFor, {
                          type: row.label,
                        })}
                        value={row[level]}
                        onChange={(event) =>
                          change(row.account_type, level, event.target.value as CashControlAction)
                        }
                        className="min-h-touch-target rounded-md border border-border-strong bg-surface px-2 text-sm text-fg"
                      >
                        {ACTIONS.map((action) => (
                          <option key={action} value={action}>
                            {label(action)}
                          </option>
                        ))}
                      </select>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button type="button" onClick={() => void save()} disabled={!rows || busy}>
            {fm(cash.save)}
          </Button>
          <p role="status" className="text-sm text-fg">
            {status === "saved" ? fm(cash.saved) : null}
          </p>
          {status === "failed" ? (
            <p role="alert" className="text-sm text-fg-danger">
              {fm(cash.saveFailed)}
            </p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
