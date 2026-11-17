"use client";

/**
 * Payment-due notice — the dunning banner (U-04-T13): in the shell's banner slot (outside the work
 * area, like the read-only notice) while the organisation's payment is overdue and its grace
 * period runs (entitlements reason `past_due`). It says when access becomes read-only and what to
 * do: the owner gets one-click "Update payment method" (Stripe's customer portal), everyone else
 * is told to ask the owner. An account-state notice, never a promotion (gap-12).
 */
import { Button, formatDate, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useState } from "react";

import { openPortal } from "@/billing/api";
import { defineMessages, useFormatMessage } from "@/i18n";

import { useEntitlements } from "./store";

const messages = defineMessages({
  label: {
    id: "entitlements.paymentDue.label",
    defaultMessage: "Payment overdue",
    description: "Accessible name of the payment-due notice region",
  },
  text: {
    id: "entitlements.paymentDue.text",
    defaultMessage:
      "The subscription payment didn't go through. Everything works until {date}; after that the organisation becomes read-only.",
    description: "Payment-due notice",
  },
  update: {
    id: "entitlements.paymentDue.update",
    defaultMessage: "Update payment method",
    description: "Payment-due notice action for the owner: opens Stripe's page",
  },
  askOwner: {
    id: "entitlements.paymentDue.askOwner",
    defaultMessage: "Ask the organisation's owner to update the payment method.",
    description: "Payment-due notice text for everyone but the owner",
  },
  failed: {
    id: "entitlements.paymentDue.failed",
    defaultMessage: "The payment page didn't open. Try again in a moment.",
    description: "Error",
  },
});

export function PaymentDueNotice() {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const { org, data } = useEntitlements();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!data || data.mode !== "full" || data.reason !== "past_due" || !data.grace_until) return null;
  const date = formatDate(new Date(data.grace_until), { locale, timeZone: data.time_zone });
  const owner = data.viewer.can_change_package;

  const update = async () => {
    if (!org) return;
    setBusy(true);
    const answer = await openPortal(org);
    setBusy(false);
    if (answer.status === 201) window.location.assign(answer.body.url);
    else setError(fm(messages.failed));
  };

  return (
    <section
      aria-label={fm(messages.label)}
      data-payment-due
      className="border-b border-border bg-surface-warning-subtle px-4 py-3 text-sm text-fg md:px-6"
    >
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <strong className="font-semibold">{fm(messages.text, { date })}</strong>
        {owner ? (
          <Button size="sm" variant="primary" disabled={busy} onClick={() => void update()}>
            {fm(messages.update)}
          </Button>
        ) : (
          <span>{fm(messages.askOwner)}</span>
        )}
        {error ? <span role="alert">{error}</span> : null}
      </p>
    </section>
  );
}
