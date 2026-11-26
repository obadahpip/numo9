"use client";

/**
 * A trip on the expense claim form (E-04-T09) with its **mileage calculator** (E-04-T10): date,
 * from, to and the kilometres driven; the amount at the CRA rate in force on the date is shown
 * **live** as the kilometres are typed, with the tiers when the trip crosses the 5,000 km
 * threshold. The rate and the kilometres already claimed this year on other claims come from
 * `GET expense-claims/mileage-rate` (once per date); the earlier trips of this form are added
 * here (`priorKm`). The server prices the trip again when the claim is saved — same arithmetic
 * (`mileage.ts`).
 */
import { Button, Input, formatMoney, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { expenseClaimsApi, type MileageRate } from "./api";
import { Labelled, type FormLine } from "./fields";
import { fm as fmm } from "./formMessages";
import { mileageAmount, priorKm } from "./mileage";

const rates = new Map<string, Promise<MileageRate | null>>();

/** The rate on `date` (cached per organisation, claim and date for the page's life). */
export function rateFor(org: string, date: string, claimId?: string): Promise<MileageRate | null> {
  const key = `${org}|${claimId ?? ""}|${date}`;
  let found = rates.get(key);
  if (!found) {
    found = expenseClaimsApi
      .mileageRate(org, date, claimId)
      .then((result) => (result.status === 200 ? result.body : null))
      .catch(() => null);
    rates.set(key, found);
  }
  return found;
}

/** Tests: forget the cached rates. */
export function clearRates(): void {
  rates.clear();
}

export interface MileageLineProps {
  org: string;
  claimId?: string;
  line: FormLine;
  index: number;
  lines: FormLine[];
  onChange: (patch: Partial<FormLine>) => void;
  onRemove: () => void;
}

export function MileageLine({
  org,
  claimId,
  line,
  index,
  lines,
  onChange,
  onRemove,
}: MileageLineProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [rate, setRate] = useState<MileageRate | null | undefined>(undefined);

  useEffect(() => {
    let live = true;
    if (!/^\d{4}-\d{2}-\d{2}$/.test(line.date)) return;
    void rateFor(org, line.date, claimId).then((found) => {
      if (live) setRate(found);
    });
    return () => {
      live = false;
    };
  }, [org, claimId, line.date]);

  const priced = rate
    ? mileageAmount(line.km, rate, priorKm(line, lines, rate.year_to_date_km))
    : null;
  const money = (value: string) => formatMoney(value, { locale });
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="text-sm font-semibold text-fg">
        {fm(fmm.tripLegend, { n: index + 1 })}
      </legend>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        <Labelled id={`${ids}-date`} label={fm(fmm.date)}>
          <Input
            id={`${ids}-date`}
            type="date"
            value={line.date}
            onChange={(e) => onChange({ date: e.target.value })}
          />
        </Labelled>
        <Labelled id={`${ids}-from`} label={fm(fmm.from)}>
          <Input
            id={`${ids}-from`}
            value={line.fromPlace}
            onChange={(e) => onChange({ fromPlace: e.target.value })}
          />
        </Labelled>
        <Labelled id={`${ids}-to`} label={fm(fmm.to)}>
          <Input
            id={`${ids}-to`}
            value={line.toPlace}
            onChange={(e) => onChange({ toPlace: e.target.value })}
          />
        </Labelled>
        <Labelled id={`${ids}-km`} label={fm(fmm.km)}>
          <Input
            id={`${ids}-km`}
            inputMode="decimal"
            numeric
            value={line.km}
            onChange={(e) => onChange({ km: e.target.value.replace(/[^0-9.]/g, "") })}
          />
        </Labelled>
      </div>
      <div className="flex flex-col gap-1" aria-live="polite" data-mileage-amount="">
        {rate === null ? (
          <p className="text-sm text-fg-muted">{fm(fmm.rateMissing)}</p>
        ) : priced ? (
          <>
            <p className="flex flex-wrap gap-1 text-sm text-fg">
              <span>{fm(fmm.mileageAmount)}</span>
              <strong className="tabular-nums">{money(priced.amount)}</strong>
            </p>
            <ul className="text-xs text-fg-muted">
              {priced.tiers.map((tier) => (
                <li key={tier.tier}>
                  {fm(fmm.mileageTier, {
                    km: tier.km,
                    rate: money(tier.rate),
                    amount: money(tier.amount),
                  })}
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </div>
      <div>
        <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
          {fm(fmm.remove)}
        </Button>
      </div>
    </fieldset>
  );
}
