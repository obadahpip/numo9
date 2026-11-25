"use client";

/**
 * A registration's filing periods (G-03a): the timeline (T18), "Change frequency" (wizard,
 * T19), "Add out-of-cycle period" (dialog, T20) and the frequency history (T21). Every change
 * is previewed before it is saved; after a change the periods and the history are read again.
 */
import { Button, EmptyState, ErrorState, SkeletonText } from "@numo9/ui";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { filingApi, type FilingCycle, type FilingPeriod, type PeriodsResponse } from "./api";
import { ChangeFrequencyWizard } from "./ChangeFrequencyWizard";
import { CycleHistory } from "./CycleHistory";
import { FilingTimeline } from "./FilingTimeline";
import { fmsg } from "./messages";
import { OutOfCycleDialog } from "./OutOfCycleDialog";
import { taxSettingsUrl } from "../settings/links";

export interface FilingScreenProps {
  org: string;
  registration: string;
  /** Whether the person may change the cycle (tax.manage). */
  canManage?: boolean;
}

export function FilingScreen({ org, registration, canManage = false }: FilingScreenProps) {
  const fm = useFormatMessage();
  const [data, setData] = useState<PeriodsResponse | null>(null);
  const [cycles, setCycles] = useState<FilingCycle[]>([]);
  const [failed, setFailed] = useState(false);
  const [wizard, setWizard] = useState(false);
  const [custom, setCustom] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setFailed(false);
    const [periods, history] = await Promise.all([
      filingApi.periods(org, registration),
      filingApi.cycles(org, registration),
    ]);
    if (periods.status === 200 && history.status === 200) {
      setData(periods.body);
      setCycles(history.body.results);
    } else setFailed(true);
  }, [org, registration]);

  useEffect(() => {
    void load();
  }, [load]);

  function saved() {
    setNotice(fm(fmsg.saved));
    void load();
  }

  async function removeCustom(period: FilingPeriod) {
    setError("");
    const result = await filingApi.removeCustom(org, registration, period.id);
    if (result.status === 200) saved();
    else setError(result.body?.detail || fm(fmsg.failed));
  }

  if (failed) {
    return (
      <ErrorState
        title={fm(fmsg.loadFailed)}
        retryLabel={fm(fmsg.retry)}
        onRetry={() => void load()}
      />
    );
  }
  if (!data) return <SkeletonText lines={4} />;
  const current = [...cycles].reverse().find((c) => c.effective_from <= data.today) ?? cycles[0];
  const setButton = (
    <Button key="set" variant="primary" onClick={() => setWizard(true)}>
      {fm(cycles.length ? fmsg.changeFrequency : fmsg.setFrequency)}
    </Button>
  );

  return (
    <div className="flex flex-col gap-6" data-filing-screen="">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            href={taxSettingsUrl(org, "registrations")}
            className="text-sm text-fg underline"
            data-tax-settings-link="registrations"
          >
            {fm(fmsg.backToSettings)}
          </Link>
          <h1 className="text-xl font-semibold text-fg">{fm(fmsg.title)}</h1>
          <p className="text-sm font-medium text-fg">
            {fm(fmsg.registration, { number: data.registration.number })}
          </p>
          <p className="text-sm text-fg-muted">{fm(fmsg.intro)}</p>
        </div>
        {canManage && data.results.length ? (
          <div className="flex flex-wrap gap-2">
            {setButton}
            <Button variant="secondary" onClick={() => setCustom(true)}>
              {fm(fmsg.addCustom)}
            </Button>
          </div>
        ) : null}
      </header>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <p role="status" className="text-sm text-fg-success" data-notice="">
        {notice}
      </p>
      {data.results.length ? (
        <FilingTimeline
          periods={data.results}
          cycles={cycles}
          onRemoveCustom={canManage ? (period) => void removeCustom(period) : undefined}
        />
      ) : (
        <EmptyState
          title={fm(fmsg.noPeriods)}
          body={fm(fmsg.noPeriodsBody)}
          actions={canManage ? [setButton] : []}
        />
      )}
      <CycleHistory cycles={cycles} today={data.today} />
      {canManage ? (
        <>
          <ChangeFrequencyWizard
            org={org}
            registration={registration}
            open={wizard}
            onOpenChange={setWizard}
            current={current?.frequency ?? null}
            defaultDate={cycles.length ? "" : (data.registration.start_date ?? "")}
            onSaved={saved}
          />
          <OutOfCycleDialog
            org={org}
            registration={registration}
            open={custom}
            onOpenChange={setCustom}
            onSaved={saved}
          />
        </>
      ) : null}
    </div>
  );
}
