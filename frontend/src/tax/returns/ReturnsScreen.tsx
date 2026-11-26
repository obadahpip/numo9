"use client";

/**
 * The GST/HST returns (G-03-T11), `/o/:org/tax/returns`: a registration's filing periods, each
 * with its return (status, version) or "Prepare return"; preparing opens the worksheet. A filed
 * period shows the lock (G-03-T12).
 */
import {
  Button,
  EmptyState,
  ErrorState,
  LockIcon,
  SkeletonText,
  formatDate,
  type AppLocale,
} from "@numo9/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import type { Registration } from "@/settings/general/registrations";
import { useFormatMessage } from "@/i18n";
import { filingApi, type FilingPeriod } from "@/tax/filing/api";

import { returnUrl, returnsApi, type TaxReturn } from "./api";
import { retm } from "./messages";
import { returnRegistrations } from "./registrations";

export function ReturnsScreen({ org }: { org: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const router = useRouter();
  const [registrations, setRegistrations] = useState<Registration[] | null>(null);
  const [chosen, setChosen] = useState("");
  const [periods, setPeriods] = useState<FilingPeriod[] | null>(null);
  const [returns, setReturns] = useState<TaxReturn[]>([]);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const loadRegistrations = useCallback(async () => {
    setFailed(false);
    const answer = await returnRegistrations(org);
    if (answer.status !== 200 || !answer.body) return setFailed(true);
    const filing = answer.body.filter((r) => r.type === "rt");
    setRegistrations(filing);
    setChosen((current) => current || filing[0]?.id || "");
  }, [org]);

  useEffect(() => {
    void loadRegistrations();
  }, [loadRegistrations]);

  const loadPeriods = useCallback(async () => {
    if (!chosen) return;
    setPeriods(null);
    const [found, made] = await Promise.all([
      filingApi.periods(org, chosen),
      returnsApi.list(org, chosen),
    ]);
    if (found.status !== 200 || made.status !== 200) return setFailed(true);
    setPeriods([...found.body.results].reverse());
    setReturns(made.body.returns);
  }, [org, chosen]);

  useEffect(() => {
    void loadPeriods();
  }, [loadPeriods]);

  async function prepare(period: string) {
    setBusy(period);
    setError("");
    const answer = await returnsApi.generate(org, period);
    setBusy("");
    if (answer.status === 201) router.push(returnUrl(org, answer.body.id));
    else setError(answer.body?.detail ?? fm(retm.loadFailed));
  }

  if (failed) {
    return (
      <ErrorState
        title={fm(retm.loadFailed)}
        retryLabel={fm(retm.retry)}
        onRetry={() => void loadRegistrations()}
      />
    );
  }

  const latest = (period: string) =>
    returns.filter((r) => r.period.id === period).sort((a, b) => b.version - a.version)[0];

  return (
    <div className="flex flex-col gap-4" data-testid="returns-screen">
      <div>
        <h1 className="text-xl font-semibold">{fm(retm.listTitle)}</h1>
        <p className="text-sm text-fg-muted">{fm(retm.listIntro)}</p>
      </div>
      {registrations === null ? (
        <SkeletonText lines={4} />
      ) : registrations.length === 0 ? (
        <EmptyState title={fm(retm.noRegistration)} compact />
      ) : (
        <>
          {registrations.length > 1 ? (
            <label className="flex max-w-sm flex-col text-sm">
              {fm(retm.registration)}
              <select
                className="rounded-md border border-border-strong px-2 py-2"
                value={chosen}
                onChange={(e) => setChosen(e.target.value)}
              >
                {registrations.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.display_number || r.number}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {error ? (
            <p role="alert" className="text-sm text-fg-danger">
              {error}
            </p>
          ) : null}
          {periods === null ? (
            <SkeletonText lines={4} />
          ) : periods.length === 0 ? (
            <EmptyState title={fm(retm.noPeriods)} compact />
          ) : (
            <table className="w-full max-w-4xl text-sm" data-testid="returns-periods">
              <thead>
                <tr className="text-fg-muted">
                  <th className="py-1 text-start font-medium">{fm(retm.period)}</th>
                  <th className="py-1 text-start font-medium">{fm(retm.due)}</th>
                  <th className="py-1 text-start font-medium">{fm(retm.statusHeading)}</th>
                  <th className="py-1 text-end font-medium">
                    <span className="sr-only">{fm(retm.actionsHeading)}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {periods.map((period) => {
                  const made = latest(period.id);
                  const locked = period.status === "filed" || period.status === "paid";
                  return (
                    <tr
                      key={period.id}
                      className="border-t border-border"
                      data-period={period.start}
                    >
                      <td className="py-2">
                        <span className="inline-flex items-center gap-1">
                          {locked ? (
                            <span
                              role="img"
                              aria-label={fm(retm.locked)}
                              data-testid="period-lock"
                              className="inline-flex"
                            >
                              <LockIcon />
                            </span>
                          ) : null}
                          {fm(retm.range, {
                            start: formatDate(period.start, { locale }),
                            end: formatDate(period.end, { locale }),
                          })}
                        </span>
                      </td>
                      <td className="py-2">{formatDate(period.due_date, { locale })}</td>
                      <td className="py-2">
                        {made && made.version > 1
                          ? fm(retm.statusVersion, { status: made.status, version: made.version })
                          : fm(retm.status, { status: made?.status ?? "none" })}
                      </td>
                      <td className="py-2 text-end">
                        {made ? (
                          <Link href={returnUrl(org, made.id)}>{fm(retm.open)}</Link>
                        ) : (
                          <Button
                            size="sm"
                            loading={busy === period.id}
                            disabled={busy !== ""}
                            onClick={() => void prepare(period.id)}
                          >
                            {fm(retm.prepare)}
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
