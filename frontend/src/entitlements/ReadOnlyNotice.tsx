"use client";

/**
 * Read-only organisation notice — the plan's "read-only org header banner" (U-03-T12): in the
 * shell's banner slot, under the top navigation and outside the work area, on every page while the
 * organisation's entitlements are in `read_only` mode. It states the exact reason and the date it
 * started, that everything can still be seen and exported, and what to do: the owner gets
 * "Reactivate the subscription" (Settings → Subscription), everyone else is told to ask the
 * owner. It is an account-state notice, never a promotion: nothing shows in any other mode, so
 * the gap-12 rule (no promotional or announcement banners in work screens) holds.
 */
import { formatDate, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";

import { defineMessages, useFormatMessage, type MessageDescriptor } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

import { useEntitlements } from "./store";

const messages = defineMessages({
  label: {
    id: "entitlements.banner.label",
    defaultMessage: "Organisation status",
    description: "Accessible name of the read-only banner region",
  },
  paymentFailed: {
    id: "entitlements.banner.paymentFailed",
    defaultMessage:
      "This organisation has been read-only since {date}: the payment failed and the grace period ended.",
    description: "Read-only banner: after a failed payment",
  },
  trialEnded: {
    id: "entitlements.banner.trialEnded",
    defaultMessage: "This organisation has been read-only since {date}: the free trial ended.",
    description: "Read-only banner: the trial ended without a subscription",
  },
  cancelled: {
    id: "entitlements.banner.cancelled",
    defaultMessage:
      "This organisation has been read-only since {date}: the subscription was cancelled.",
    description: "Read-only banner: cancelled subscription",
  },
  platform: {
    id: "entitlements.banner.platform",
    defaultMessage: "This organisation has been read-only since {date}: Numo9 set it read-only.",
    description: "Read-only banner: set by the platform",
  },
  other: {
    id: "entitlements.banner.other",
    defaultMessage: "This organisation has been read-only since {date}.",
    description: "Read-only banner: any other reason",
  },
  readable: {
    id: "entitlements.banner.readable",
    defaultMessage: "You can still see and export everything.",
    description: "Read-only banner: what still works",
  },
  reactivate: {
    id: "entitlements.banner.reactivate",
    defaultMessage: "Reactivate the subscription",
    description: "Read-only banner action for the owner: opens Settings → Subscription",
  },
  askOwner: {
    id: "entitlements.banner.askOwner",
    defaultMessage: "Ask the organisation's owner to reactivate it.",
    description: "Read-only banner text for everyone but the owner",
  },
});

const REASONS: Record<string, MessageDescriptor> = {
  payment_failed: messages.paymentFailed,
  trial_ended: messages.trialEnded,
  cancelled: messages.cancelled,
  platform: messages.platform,
};

export function ReadOnlyNotice() {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const { org, data } = useEntitlements();
  if (!data || data.mode !== "read_only") return null;
  const since = data.since ? new Date(data.since) : null;
  const date = since ? formatDate(since, { locale, timeZone: data.time_zone }) : "—";
  const owner = data.viewer.can_change_package;
  return (
    <section
      aria-label={fm(messages.label)}
      data-read-only-reason={data.reason}
      className="border-b border-border bg-surface-warning-subtle px-4 py-3 text-sm text-fg md:px-6"
    >
      <p className="flex flex-wrap gap-x-1">
        <strong className="font-semibold">
          {fm(REASONS[data.reason] ?? messages.other, { date })}
        </strong>
        <span>{fm(messages.readable)}</span>
        {owner && org ? (
          <a
            href={orgModuleUrl(org, "settings/subscription")}
            className="font-semibold underline underline-offset-2"
          >
            {fm(messages.reactivate)}
          </a>
        ) : (
          <span>{fm(messages.askOwner)}</span>
        )}
      </p>
    </section>
  );
}
