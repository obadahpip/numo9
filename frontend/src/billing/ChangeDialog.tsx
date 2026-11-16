"use client";

import { Button, Dialog, formatDate, LoadingRegion, SkeletonText } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";
import type { AppLocale } from "@/i18n/locales";

import {
  changePackage,
  previewChange,
  type BillingSubscription,
  type ChangePreview,
  type Interval,
} from "./api";
import { money } from "./money";

const m = defineMessages({
  title: {
    id: "billing.change.title",
    defaultMessage: "Change to {package}?",
    description: "Dialog title",
  },
  colNow: { id: "billing.change.colNow", defaultMessage: "Now", description: "Comparison column" },
  colAfter: {
    id: "billing.change.colAfter",
    defaultMessage: "After the change",
    description: "Comparison column",
  },
  rowPackage: { id: "billing.change.rowPackage", defaultMessage: "Package", description: "Row" },
  rowPrice: { id: "billing.change.rowPrice", defaultMessage: "Price", description: "Row" },
  price: {
    id: "billing.change.price",
    defaultMessage: "{amount} {interval, select, year {per year} other {per month}}",
    description: "A price in the comparison",
  },
  upgrade: {
    id: "billing.change.upgrade",
    defaultMessage:
      "You'll be charged {amount} today: the new price for the rest of this period, less what you've already paid for it.",
    description: "Upgrade: the prorated charge (Stripe's preview)",
  },
  downgrade: {
    id: "billing.change.downgrade",
    defaultMessage:
      "Nothing to pay today. You keep {current} until {date}; from then on you'll pay {amount}.",
    description: "Downgrade at the end of the period",
  },
  loading: {
    id: "billing.change.loading",
    defaultMessage: "Working out the price…",
    description: "Screen-reader text while the preview loads",
  },
  confirm: {
    id: "billing.change.confirm",
    defaultMessage: "Confirm change",
    description: "Button",
  },
  cancel: { id: "billing.change.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "billing.change.close", defaultMessage: "Close", description: "Dialog close" },
  done: {
    id: "billing.change.done",
    defaultMessage: "Your package is now {package}.",
    description: "Status after an upgrade",
  },
  scheduled: {
    id: "billing.change.scheduled",
    defaultMessage: "Your package changes to {package} on {date}.",
    description: "Status after a downgrade",
  },
  failed: {
    id: "billing.change.failed",
    defaultMessage: "The package didn't change. Try again in a moment.",
    description: "Error",
  },
});

/**
 * Proration comparison (U-04-T13): the current and the new package side by side, and Stripe's own
 * figure for today — "You'll be charged $25.13 today" on an upgrade, nothing on a downgrade (it
 * takes effect at the period end). Confirming sends the preview's proration date, so the charge
 * equals what was shown.
 */
export function ChangeDialog({
  org,
  target,
  interval,
  current,
  onClose,
  onDone,
}: Readonly<{
  org: string;
  target: { code: string; name: string };
  interval: Interval;
  current: BillingSubscription | null;
  onClose: () => void;
  onDone: (message: string) => void;
}>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [preview, setPreview] = useState<ChangePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    void previewChange(org, target.code, interval).then((answer) => {
      if (!live) return;
      if (answer.status === 200) setPreview(answer.body);
      else setError(fm(m.failed));
    });
    return () => {
      live = false;
    };
  }, [org, target.code, interval, fm]);

  const date = (iso: string) => formatDate(new Date(iso), { locale });
  const confirm = async () => {
    if (!preview) return;
    setBusy(true);
    const answer = await changePackage(org, {
      package: target.code,
      interval,
      proration_date: preview.proration_date,
    });
    setBusy(false);
    if (answer.status !== 200) {
      setError(fm(m.failed));
      return;
    }
    onDone(
      answer.body.kind === "upgrade"
        ? fm(m.done, { package: target.name })
        : fm(m.scheduled, { package: target.name, date: date(answer.body.effective_at) }),
    );
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => (open ? null : onClose())}
      title={fm(m.title, { package: target.name })}
      closeLabel={fm(m.close)}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {fm(m.cancel)}
          </Button>
          <Button variant="primary" disabled={busy || !preview} onClick={() => void confirm()}>
            {fm(m.confirm)}
          </Button>
        </>
      }
    >
      {preview ? (
        <div className="flex flex-col gap-4" data-change-preview={preview.kind}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-fg-muted">
                <td />
                <th scope="col" className="py-2 text-start">
                  {fm(m.colNow)}
                </th>
                <th scope="col" className="py-2 text-start">
                  {fm(m.colAfter)}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border">
                <th scope="row" className="py-2 pe-3 text-start font-normal text-fg-muted">
                  {fm(m.rowPackage)}
                </th>
                <td className="py-2">{current?.package?.name}</td>
                <td className="py-2 font-semibold">{target.name}</td>
              </tr>
              <tr>
                <th scope="row" className="py-2 pe-3 text-start font-normal text-fg-muted">
                  {fm(m.rowPrice)}
                </th>
                <td className="py-2">
                  {current
                    ? fm(m.price, {
                        amount: money(current.amount_cents, locale),
                        interval: current.interval,
                      })
                    : null}
                </td>
                <td className="py-2 font-semibold">
                  {fm(m.price, { amount: money(preview.amount_cents, locale), interval })}
                </td>
              </tr>
            </tbody>
          </table>
          <p data-charge>
            {preview.kind === "upgrade"
              ? fm(m.upgrade, { amount: money(preview.charged_today_cents, locale) })
              : fm(m.downgrade, {
                  current: current?.package?.name ?? "",
                  date: date(preview.effective_at),
                  amount: fm(m.price, { amount: money(preview.amount_cents, locale), interval }),
                })}
          </p>
        </div>
      ) : error ? null : (
        <LoadingRegion label={fm(m.loading)}>
          <SkeletonText lines={3} />
        </LoadingRegion>
      )}
      {error ? (
        <p role="alert" className="text-fg-danger">
          {error}
        </p>
      ) : null}
    </Dialog>
  );
}
