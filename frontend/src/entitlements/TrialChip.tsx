"use client";

/**
 * Trial chip (U-05-T10) — in the header while the organisation is on its free trial (entitlements
 * reason `trialing`): "Trial — 12 days left". Neutral above 7 days, amber at 7 or fewer, red on
 * the last day — and the words always say how long is left (never colour alone, gap-41: every role
 * sees the plan state). It opens a drawer comparing the packages (what each includes, the trial's
 * package marked) with "Choose a package" for whoever may change it.
 */
import { Drawer, formatDate, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { getOrganisationMatrix, type OrganisationMatrix } from "@/catalogue/api";
import { defineMessages, useFormatMessage } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

import { useEntitlements } from "./store";

const messages = defineMessages({
  chip: {
    id: "entitlements.trial.chip",
    defaultMessage:
      "{days, plural, =0 {Trial — last day} one {Trial — # day left} other {Trial — # days left}}",
    description: "Header chip during the free trial",
  },
  title: {
    id: "entitlements.trial.title",
    defaultMessage: "Your free trial",
    description: "Title of the trial drawer",
  },
  ends: {
    id: "entitlements.trial.ends",
    defaultMessage:
      "The trial ends on {date}. Choose a package before then to keep working without a break — everything you entered stays.",
    description: "Trial drawer: when the trial ends",
  },
  trying: {
    id: "entitlements.trial.trying",
    defaultMessage: "You're trying {package}.",
    description: "Trial drawer: the package the trial gives",
  },
  compare: {
    id: "entitlements.trial.compare",
    defaultMessage: "Compare packages",
    description: "Heading of the package comparison in the trial drawer",
  },
  includes: {
    id: "entitlements.trial.includes",
    defaultMessage: "Includes {products}",
    description: "What a package includes (product names)",
  },
  current: {
    id: "entitlements.trial.current",
    defaultMessage: "Your trial",
    description: "Badge on the package the trial gives",
  },
  choose: {
    id: "entitlements.trial.choose",
    defaultMessage: "Choose a package",
    description: "Link to the subscription page",
  },
  askOwner: {
    id: "entitlements.trial.askOwner",
    defaultMessage: "The organisation's owner chooses the package.",
    description: "Trial drawer text for everyone but the owner",
  },
  close: { id: "entitlements.trial.close", defaultMessage: "Close", description: "Drawer close" },
  loading: {
    id: "entitlements.trial.loading",
    defaultMessage: "Loading packages…",
    description: "Trial drawer while the packages load",
  },
});

export type TrialTone = "neutral" | "warning" | "danger";

/** The chip's tone: amber at 7 days or fewer, red on the last day (1 or 0 days left). */
export function trialTone(days: number): TrialTone {
  if (days <= 1) return "danger";
  if (days <= 7) return "warning";
  return "neutral";
}

const TONES: Record<TrialTone, string> = {
  neutral: "border-border-strong bg-surface text-fg",
  warning: "border-border-strong bg-surface-warning-subtle text-fg-warning",
  danger: "border-border-danger bg-surface-danger-subtle text-fg-danger",
};

export function TrialChip() {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const { org, data } = useEntitlements();
  const [open, setOpen] = useState(false);
  const [matrix, setMatrix] = useState<OrganisationMatrix | null>(null);
  useEffect(() => {
    if (!open || !org || matrix) return;
    void getOrganisationMatrix(org).then((result) => {
      if (result.status === 200 && "packages" in result.body)
        setMatrix(result.body as OrganisationMatrix);
    });
  }, [open, org, matrix]);
  if (!org || !data || data.reason !== "trialing" || data.trial_days_left == null) return null;
  const days = data.trial_days_left;
  const tone = trialTone(days);
  const ends = data.trial_ends_at
    ? formatDate(new Date(data.trial_ends_at), { locale, timeZone: data.time_zone })
    : "";
  const names = data.product_names;
  return (
    <>
      <button
        type="button"
        data-trial-chip={tone}
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
        className={`inline-flex min-h-8 items-center rounded-full border px-3 text-xs font-bold ${TONES[tone]}`}
      >
        {fm(messages.chip, { days })}
      </button>
      <Drawer
        open={open}
        onOpenChange={setOpen}
        title={fm(messages.title)}
        description={fm(messages.ends, { date: ends })}
        closeLabel={fm(messages.close)}
        size="md"
      >
        <div className="flex flex-col gap-3" data-trial-drawer="">
          {data.package_name ? (
            <p className="text-sm text-fg">{fm(messages.trying, { package: data.package_name })}</p>
          ) : null}
          <h3 className="text-base font-bold text-fg">{fm(messages.compare)}</h3>
          {matrix ? (
            <ul className="flex flex-col gap-2">
              {matrix.packages.map((item) => (
                <li
                  key={item.code}
                  data-package={item.code}
                  className="rounded-md border border-border p-3"
                >
                  <p className="flex items-center gap-2 font-semibold text-fg">
                    {item.name}
                    {item.code === data.package ? (
                      <span className="rounded-full border border-border-strong px-2 text-xs">
                        {fm(messages.current)}
                      </span>
                    ) : null}
                  </p>
                  <p className="text-sm text-fg-muted">
                    {fm(messages.includes, {
                      products: item.products.map((code) => names[code] ?? code).join(", "),
                    })}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-fg-muted">{fm(messages.loading)}</p>
          )}
          {data.viewer.can_change_package ? (
            <a
              href={orgModuleUrl(org, "settings/subscription")}
              className="inline-flex min-h-touch-target items-center justify-center rounded-md bg-surface-inverse px-4 text-sm font-bold text-fg-inverse"
            >
              {fm(messages.choose)}
            </a>
          ) : (
            <p className="text-sm text-fg-muted">{fm(messages.askOwner)}</p>
          )}
        </div>
      </Drawer>
    </>
  );
}
