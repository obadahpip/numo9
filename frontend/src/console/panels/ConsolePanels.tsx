"use client";

/**
 * Console home panels (U-06-T13): the founding counter ("427/1,000", from U-08) with a link to
 * the founding offer screen, and the demo manager (U-07): every open demo with its last activity
 * and the day the inactivity purge takes it, and a confirmed "Purge now" (platform owners).
 */
import { Button, Dialog, ErrorState, formatDate } from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { getFounding, type FoundingOverview } from "@/console/founding/api";
import { useFormatMessage } from "@/i18n";

import { getDemos, purgeDemo, type DemoOverview, type DemoRow } from "./api";
import { m } from "./messages";

function useLoad<T>(load: () => Promise<{ status: number; body: unknown }>) {
  const [data, setData] = useState<T | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let cancelled = false;
    void load().then((result) => {
      if (cancelled) return;
      if (result.status === 200) {
        setData(result.body as T);
        setFailed(false);
      } else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [attempt, load]);
  return { data, setData, failed, retry: () => setAttempt((n) => n + 1) };
}

export function FoundingCounterPanel() {
  const fm = useFormatMessage();
  const { data, failed, retry } = useLoad<FoundingOverview>(getFounding);
  return (
    <section
      aria-labelledby="console-panel-founding"
      className="flex flex-col gap-2 rounded-lg border border-border p-4"
      data-panel="founding"
    >
      <h2 id="console-panel-founding" className="text-lg font-semibold text-fg">
        {fm(m.foundingTitle)}
      </h2>
      {failed ? (
        <ErrorState
          title={fm(m.loadFailed)}
          retryLabel={fm(m.retry)}
          onRetry={retry}
          headingLevel={3}
        />
      ) : data ? (
        <>
          <p className="text-3xl font-bold text-fg tabular-nums" data-founding-counter="">
            <span aria-hidden="true">
              {fm(m.foundingCounter, { allocated: data.allocated, cap: data.cap })}
            </span>
            <span className="sr-only">
              {fm(m.foundingCounterLabel, { allocated: data.allocated, cap: data.cap })}
            </span>
          </p>
          <p className="text-sm text-fg-muted">
            {data.remaining > 0
              ? fm(m.foundingLeft, { remaining: data.remaining })
              : fm(m.foundingComplete)}
          </p>
          <Link href="/console/founding" className="text-sm font-semibold text-fg underline">
            {fm(m.foundingOpen)}
          </Link>
        </>
      ) : null}
    </section>
  );
}

export function DemoManagerPanel() {
  const fm = useFormatMessage();
  const locale = useLocale() as "en-CA" | "fr-CA";
  const { data, setData, failed, retry } = useLoad<DemoOverview>(getDemos);
  const [status, setStatus] = useState("");
  const date = (value: string) =>
    formatDate(new Date(value), { locale, timeZone: "America/Toronto" });
  const day = (iso: string) => formatDate(iso, { locale });

  return (
    <section
      aria-labelledby="console-panel-demos"
      className="flex flex-col gap-3 rounded-lg border border-border p-4"
      data-panel="demos"
    >
      <h2 id="console-panel-demos" className="text-lg font-semibold text-fg">
        {fm(m.demosTitle)}
      </h2>
      <p role="status" className="sr-only">
        {status}
      </p>
      {failed ? (
        <ErrorState
          title={fm(m.loadFailed)}
          retryLabel={fm(m.retry)}
          onRetry={retry}
          headingLevel={3}
        />
      ) : data ? (
        <>
          <p className="text-sm text-fg">
            {fm(m.demosSummary, {
              open: data.open,
              soon: data.purge_soon,
              version: data.seed_version,
            })}
          </p>
          <p className="text-sm text-fg-muted">{fm(m.demosRule, { days: data.idle_days })}</p>
          {data.demos.length === 0 ? (
            <p className="text-sm text-fg-muted">{fm(m.demosEmpty)}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-start text-sm">
                <caption className="sr-only">{fm(m.demosCaption)}</caption>
                <thead>
                  <tr className="border-b border-border text-fg-muted">
                    <th scope="col" className="py-2 pe-3 text-start">
                      {fm(m.demoName)}
                    </th>
                    <th scope="col" className="py-2 pe-3 text-start">
                      {fm(m.demoLastActive)}
                    </th>
                    <th scope="col" className="py-2 pe-3 text-start">
                      {fm(m.demoPurgeOn)}
                    </th>
                    <th scope="col" className="py-2 pe-3 text-end">
                      {fm(m.demoMembers)}
                    </th>
                    <th scope="col" className="py-2 text-end">
                      {fm(m.demoActions)}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.demos.map((demo) => (
                    <tr key={demo.id} className="border-b border-border" data-demo={demo.id}>
                      <td className="py-2 pe-3">{demo.name}</td>
                      <td className="py-2 pe-3">
                        {demo.last_active_at ? date(demo.last_active_at) : fm(m.demoNever)}
                      </td>
                      <td className="py-2 pe-3">{day(demo.purge_on)}</td>
                      <td className="py-2 pe-3 text-end tabular-nums">{demo.members}</td>
                      <td className="py-2 text-end">
                        <PurgeButton
                          demo={demo}
                          onPurged={() => {
                            setData({
                              ...data,
                              open: data.open - 1,
                              demos: data.demos.filter((d) => d.id !== demo.id),
                            });
                            setStatus(fm(m.purged, { name: demo.name }));
                          }}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}

function PurgeButton({ demo, onPurged }: { demo: DemoRow; onPurged: () => void }) {
  const fm = useFormatMessage();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        setError("");
      }}
      trigger={
        <Button size="sm" variant="ghost" aria-label={fm(m.purgeLabel, { name: demo.name })}>
          {fm(m.purge)}
        </Button>
      }
      title={fm(m.purgeTitle, { name: demo.name })}
      description={fm(m.purgeBody)}
      closeLabel={fm(m.close)}
      size="sm"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setOpen(false)}>
            {fm(m.cancel)}
          </Button>
          <Button
            variant="danger"
            loading={busy}
            onClick={() => {
              setBusy(true);
              void purgeDemo(demo.id).then((result) => {
                setBusy(false);
                if (result.status === 204) {
                  setOpen(false);
                  onPurged();
                } else setError(fm(m.purgeFailed));
              });
            }}
          >
            {fm(m.purge)}
          </Button>
        </div>
      }
    >
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
    </Dialog>
  );
}
