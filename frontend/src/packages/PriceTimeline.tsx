"use client";

import {
  Button,
  Dialog,
  Input,
  Select,
  addDays,
  cn,
  compareIso,
  formatDate,
  parseIso,
  type AppLocale,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import {
  errorText,
  fieldErrors,
  ok,
  packagesApi,
  type Interval,
  type PackagePrice,
  type PlatformPackage,
  type PriceImpact,
} from "./api";
import { pm, tm } from "./messages";
import { money, parseCents } from "./money";

const DAY = 24 * 60 * 60 * 1000;

function days(iso: string): number {
  const parts = parseIso(iso);
  return parts ? Date.UTC(parts.year, parts.month - 1, parts.day) / DAY : 0;
}

/** The span every row of the timeline shares: first start (or today) → last change + 90 days. */
function span(prices: PackagePrice[], today: string): { from: number; to: number } {
  const points = [days(today)];
  for (const p of prices) {
    points.push(days(p.effective_from));
    if (p.effective_to) points.push(days(p.effective_to));
  }
  const from = Math.min(...points);
  return { from, to: Math.max(Math.max(...points) + 90, from + 180) };
}

/**
 * Price timeline (U-02-T10): one row per billing interval with every version as a bar from its
 * start to the next start (no end = open), the version in force today highlighted and a "today"
 * marker; scheduled versions can be deleted. "Schedule a price change" opens a dialog that shows,
 * from the API, how many subscriptions the new price affects at their next renewal before it is
 * confirmed.
 */
export function PriceTimeline({
  pkg,
  onChanged,
}: {
  pkg: PlatformPackage;
  onChanged: (next: PlatformPackage) => void;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const headingId = useId();
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const range = span(pkg.prices, pkg.today);
  const pct = (iso: string) => ((days(iso) - range.from) / (range.to - range.from)) * 100;
  const date = (iso: string) => formatDate(iso, { locale });

  const remove = async (price: PackagePrice) => {
    setError(null);
    const result = await packagesApi.deletePrice(pkg.code, price.id);
    if (result.status !== 204) {
      setError(errorText(result.body) ?? fm(pm.failed));
      return;
    }
    const fresh = await packagesApi.get(pkg.code);
    if (fresh.status === 200) onChanged(fresh.body as PlatformPackage);
    setStatus(fm(tm.deleted));
  };

  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4"
      data-testid="price-timeline"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 id={headingId} className="text-lg font-semibold">
            {fm(tm.title)}
          </h2>
          <p className="text-sm text-fg-muted">{fm(tm.intro)}</p>
        </div>
        <Button onClick={() => setOpen(true)}>{fm(tm.schedule)}</Button>
      </div>
      {status ? (
        <p role="status" className="text-sm text-fg-muted">
          {status}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      {(["month", "year"] as const).map((interval) => {
        const versions = pkg.prices.filter((p) => p.interval === interval);
        const label = interval === "month" ? fm(tm.monthly) : fm(tm.annual);
        return (
          <div key={interval} className="flex flex-col gap-2" data-interval={interval}>
            <h3 className="font-semibold">{label}</h3>
            {versions.length === 0 ? (
              <p className="text-sm text-fg-muted">{fm(tm.noVersions)}</p>
            ) : (
              <div className="relative pt-6 pb-2">
                <div
                  className="absolute top-0 bottom-0 z-10 w-0.5 bg-fg-danger"
                  style={{ insetInlineStart: `${pct(pkg.today)}%` }}
                  data-testid="today-marker"
                  aria-hidden="true"
                >
                  <span className="absolute -top-0.5 -translate-x-1/2 whitespace-nowrap text-xs font-bold text-fg-danger rtl:translate-x-1/2">
                    {fm(tm.today, { date: date(pkg.today) })}
                  </span>
                </div>
                <ol className="relative h-10 rounded bg-surface-muted" aria-label={label}>
                  {versions.map((price) => {
                    const start = pct(price.effective_from);
                    const end = price.effective_to ? pct(price.effective_to) : 100;
                    const description = fm(tm.version, {
                      amount: money(price.amount_cents, locale),
                      start: date(price.effective_from),
                      end: price.effective_to ? date(addDays(price.effective_to, -1)) : "none",
                      state: price.state,
                    });
                    return (
                      <li
                        key={price.id}
                        data-price-id={price.id}
                        data-state={price.state}
                        aria-label={description}
                        className={cn(
                          "absolute top-0 flex h-10 items-center overflow-hidden rounded border px-2 text-sm font-bold tabular-nums",
                          price.state === "current"
                            ? "border-border-strong bg-surface-accent"
                            : price.state === "scheduled"
                              ? "border-dashed border-border-strong bg-surface"
                              : "border-border bg-surface-subtle text-fg-muted",
                        )}
                        style={{
                          insetInlineStart: `${start}%`,
                          width: `calc(${Math.max(end - start, 0)}% - 2px)`,
                        }}
                      >
                        {money(price.amount_cents, locale)}
                      </li>
                    );
                  })}
                </ol>
                <ul className="mt-2 flex flex-col gap-1 text-xs text-fg-muted">
                  {versions.map((price) => (
                    <li key={price.id} className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-fg">
                        {money(price.amount_cents, locale)}
                      </span>
                      <span>
                        {fm(tm.range, {
                          start: date(price.effective_from),
                          end: price.effective_to
                            ? date(addDays(price.effective_to, -1))
                            : fm(tm.noEnd),
                        })}
                      </span>
                      <span>
                        {price.state === "current"
                          ? fm(tm.stateCurrent)
                          : price.state === "scheduled"
                            ? fm(tm.stateScheduled)
                            : fm(tm.statePast)}
                      </span>
                      {price.state === "scheduled" ? (
                        <Button
                          variant="link"
                          size="sm"
                          aria-label={fm(tm.deleteScheduled, {
                            amount: money(price.amount_cents, locale),
                            start: date(price.effective_from),
                          })}
                          onClick={() => void remove(price)}
                        >
                          {fm(tm.deleteShort)}
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        );
      })}
      <ScheduleDialog
        pkg={pkg}
        open={open}
        onClose={() => setOpen(false)}
        onScheduled={(next, message) => {
          setOpen(false);
          onChanged(next);
          setStatus(message);
        }}
      />
    </section>
  );
}

function ScheduleDialog({
  pkg,
  open,
  onClose,
  onScheduled,
}: {
  pkg: PlatformPackage;
  open: boolean;
  onClose: () => void;
  onScheduled: (next: PlatformPackage, message: string) => void;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = { interval: useId(), amount: useId(), start: useId() };
  const [interval, setInterval] = useState<Interval>("month");
  const [amount, setAmount] = useState("");
  const [start, setStart] = useState("");
  const [impact, setImpact] = useState<PriceImpact | null>(null);
  const [checking, setChecking] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [alert, setAlert] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const min = pkg.status === "draft" ? undefined : pkg.today;

  useEffect(() => {
    if (!open) {
      setAmount("");
      setStart("");
      setImpact(null);
      setErrors({});
      setAlert(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open || !/^\d{4}-\d{2}-\d{2}$/.test(start)) {
      setImpact(null);
      return;
    }
    let live = true;
    setChecking(true);
    void packagesApi.impact(pkg.code, interval, start).then((result) => {
      if (!live) return;
      setChecking(false);
      setImpact(result.status === 200 ? (result.body as PriceImpact) : null);
    });
    return () => {
      live = false;
    };
  }, [open, pkg.code, interval, start]);

  const submit = async () => {
    const local: Record<string, string> = {};
    const cents = parseCents(amount, locale);
    if (cents === null) local.amount_cents = fm(tm.amountInvalid);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || (min && compareIso(start, min) < 0))
      local.effective_from = fm(tm.startInvalid);
    setErrors(local);
    if (Object.keys(local).length || cents === null) return;
    setBusy(true);
    const result = await packagesApi.schedulePrice(pkg.code, {
      interval,
      amount_cents: cents,
      effective_from: start,
    });
    setBusy(false);
    if (ok(result.status) && "package" in result.body) {
      const body = result.body as { package: PlatformPackage };
      onScheduled(
        body.package,
        fm(tm.scheduled, {
          amount: money(cents, locale),
          interval,
          date: formatDate(start, { locale }),
        }),
      );
    } else {
      const byField = fieldErrors(result.body);
      setErrors(byField);
      setAlert(Object.keys(byField).length ? null : (errorText(result.body) ?? fm(pm.failed)));
    }
  };

  const error = (field: string, id: string) =>
    errors[field] ? (
      <p id={`${id}-error`} className="text-sm text-fg-danger">
        {errors[field]}
      </p>
    ) : null;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => (next ? undefined : onClose())}
      title={fm(tm.schedule)}
      closeLabel={fm(pm.close)}
      size="md"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {fm(pm.cancel)}
          </Button>
          <Button onClick={() => void submit()} loading={busy}>
            {fm(tm.submit)}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <span id={ids.interval} className="text-sm font-semibold">
              {fm(tm.interval)}
            </span>
            <Select
              aria-labelledby={ids.interval}
              value={interval}
              onValueChange={(v) => setInterval(v as Interval)}
              options={[
                { value: "month", label: fm(tm.monthly) },
                { value: "year", label: fm(tm.annual) },
              ]}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor={ids.amount} className="text-sm font-semibold">
              {fm(tm.amount)}
            </label>
            <Input
              id={ids.amount}
              value={amount}
              inputMode="decimal"
              numeric
              prefix="$"
              invalid={Boolean(errors.amount_cents)}
              aria-describedby={errors.amount_cents ? `${ids.amount}-error` : undefined}
              onChange={(event) => setAmount(event.target.value)}
            />
            {error("amount_cents", ids.amount)}
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor={ids.start} className="text-sm font-semibold">
              {fm(tm.start)}
            </label>
            <Input
              id={ids.start}
              type="date"
              value={start}
              min={min}
              invalid={Boolean(errors.effective_from)}
              aria-describedby={`${ids.start}-hint${errors.effective_from ? ` ${ids.start}-error` : ""}`}
              onChange={(event) => setStart(event.target.value)}
            />
            <p id={`${ids.start}-hint`} className="text-xs text-fg-muted">
              {fm(tm.startHint)}
            </p>
            {error("effective_from", ids.start)}
          </div>
        </div>
        {checking ? (
          <p className="text-sm text-fg-muted">{fm(tm.checking)}</p>
        ) : impact ? (
          <div
            className="flex flex-col gap-1 rounded-lg border-2 border-border-accent bg-surface-accent-subtle px-4 py-3"
            data-testid="price-impact"
            aria-live="polite"
          >
            <p className="font-bold">{fm(tm.affected, { count: impact.affected_subscriptions })}</p>
            {impact.current ? (
              <p className="text-sm">
                {fm(tm.keepsOld, {
                  date: formatDate(start, { locale }),
                  amount: money(impact.current.amount_cents, locale),
                })}
              </p>
            ) : null}
            <p className="text-sm">{fm(tm.grandfathered)}</p>
          </div>
        ) : null}
        {alert ? (
          <p role="alert" className="text-sm text-fg-danger">
            {alert}
          </p>
        ) : null}
      </div>
    </Dialog>
  );
}
