"use client";

import { Badge, CheckIcon, cn, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useState, type ReactNode } from "react";

import { useFormatMessage } from "@/i18n";

import type { Interval } from "./api";
import { pm } from "./messages";
import { money } from "./money";

export interface PricingCardProps {
  name: string;
  description: string;
  products: string[];
  freeProducts: string[];
  maxUsers: number | null;
  founding: boolean;
  /** Whole cents in force today per interval (null = no price). */
  prices: Record<Interval, number | null>;
  /** Accessible name of the card region. */
  label: string;
}

/**
 * The public pricing card (U-02-T09 preview): what the website's Packages & Pricing page (Q-01)
 * shows for one package — name, description, monthly/annual toggle, price before GST/HST,
 * products, free sets, user limit and the founding-offer badge. Pure presentation: the editor
 * passes the unsaved form, the website will pass `GET /api/v1/public/pricing`.
 */
export function PricingCard({
  name,
  description,
  products,
  freeProducts,
  maxUsers,
  founding,
  prices,
  label,
}: PricingCardProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [interval, setInterval] = useState<Interval>("month");
  const amount = prices[interval];
  return (
    <section
      aria-label={label}
      data-testid="pricing-card"
      className="flex flex-col gap-4 overflow-hidden rounded-xl border-2 border-border-strong bg-surface"
    >
      <div className="h-2 bg-surface-accent" aria-hidden="true" />
      <div className="flex flex-col gap-4 px-5 pb-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h3 className="text-xl font-bold" data-testid="card-name">
            {name.trim() || fm(pm.cardUntitled)}
          </h3>
          {founding ? <Badge tone="accent">{fm(pm.cardFounding)}</Badge> : null}
        </div>
        {description.trim() ? <p className="text-sm text-fg-muted">{description}</p> : null}
        <div
          role="group"
          aria-label={fm(pm.cardInterval)}
          className="inline-flex w-fit rounded-full bg-surface-muted p-1"
        >
          {(["month", "year"] as const).map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={interval === value}
              onClick={() => setInterval(value)}
              className={cn(
                "min-h-8 rounded-full px-3 text-xs font-semibold",
                interval === value ? "bg-surface-inverse text-fg-inverse" : "text-fg",
              )}
            >
              {value === "month" ? fm(pm.cardMonthly) : fm(pm.cardAnnual)}
            </button>
          ))}
        </div>
        <p className="flex flex-wrap items-baseline gap-2" data-testid="card-price">
          {amount === null ? (
            <span className="text-lg font-semibold text-fg-muted">{fm(pm.cardNoPrice)}</span>
          ) : (
            <>
              <span className="text-3xl font-bold tabular-nums">{money(amount, locale)}</span>
              <span className="text-sm text-fg-muted">
                {interval === "month" ? fm(pm.cardPerMonth) : fm(pm.cardPerYear)}
              </span>
            </>
          )}
        </p>
        <ul className="flex flex-col gap-1.5 text-sm" data-testid="card-lines">
          {products.map((product) => (
            <Line key={product}>{product}</Line>
          ))}
          {freeProducts.length > 0 ? (
            <Line>{fm(pm.cardFree, { products: freeProducts.join(", ") })}</Line>
          ) : null}
          <Line>
            {maxUsers === null ? fm(pm.cardUnlimitedUsers) : fm(pm.cardUsers, { count: maxUsers })}
          </Line>
        </ul>
        <span
          aria-hidden="true"
          className="mt-2 flex min-h-touch-target items-center justify-center rounded-md bg-surface-inverse text-sm font-bold text-fg-inverse-accent"
        >
          {fm(pm.cardTrial)}
        </span>
      </div>
    </section>
  );
}

function Line({ children }: { children: ReactNode }) {
  return (
    <li className="flex items-center gap-2">
      <span aria-hidden="true" className="text-fg-success">
        <CheckIcon />
      </span>
      {children}
    </li>
  );
}
