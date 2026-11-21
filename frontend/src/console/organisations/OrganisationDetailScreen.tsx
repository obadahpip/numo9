"use client";

/**
 * Console → one organisation (U-06-T04): status, subscription and its **history** (trial
 * started, every status change, conversion — from the audit log of the subscription), users with
 * their roles and last sign-in, the practices serving it, and the organisation's latest audit
 * events.
 */
import { Button, ErrorState, formatDate, formatDateTime, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";

import { useFormatMessage } from "@/i18n";
import { packageUrl } from "@/packages/PackagesScreen";

import { StartImpersonationDialog } from "../impersonation/StartImpersonationDialog";
import { m as im } from "../impersonation/messages";
import { usePlatformMe } from "../shell/ConsoleFrame";

import { getOrganisation, type PlatformOrganisationDetail, type TimelineItem } from "./api";
import { m } from "./messages";
import { ProductGrants } from "./ProductGrants";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-border p-4">
      <h2 className="text-lg font-bold text-fg">{title}</h2>
      {children}
    </section>
  );
}

export function OrganisationDetailScreen({ id, extra }: { id: string; extra?: ReactNode }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [data, setData] = useState<PlatformOrganisationDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [actingAs, setActingAs] = useState<{ id: string; name: string } | null>(null);
  const canImpersonate = usePlatformMe()?.permissions.includes("platform.impersonate") ?? false;
  const canEditPackages =
    usePlatformMe()?.permissions.includes("platform.catalogue.manage") ?? false;
  useEffect(() => {
    let cancelled = false;
    void getOrganisation(id).then((result) => {
      if (cancelled) return;
      if (result.status === 200) setData(result.body);
      else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [id, attempt]);
  if (failed) {
    return (
      <ErrorState
        title={fm(m.loadFailed)}
        retryLabel={fm(m.retry)}
        onRetry={() => {
          setFailed(false);
          setAttempt((n) => n + 1);
        }}
        headingLevel={2}
      />
    );
  }
  if (!data) return null;
  const zone = data.time_zone;
  const when = (iso: string) => formatDateTime(new Date(iso), { locale, timeZone: zone });
  const line = (item: TimelineItem) =>
    item.kind === "trial_started"
      ? fm(m.trialStarted)
      : item.kind === "converted"
        ? fm(m.converted)
        : item.kind === "subscribed"
          ? fm(m.subscribed, { detail: item.detail })
          : fm(m.statusChanged, { detail: item.detail });
  return (
    <div className="flex flex-col gap-4" data-console-organisation={data.id}>
      <Link href="/console/organisations" className="text-sm font-semibold text-fg underline">
        {fm(m.back)}
      </Link>
      <div>
        <h1 className="text-2xl font-bold text-fg">{data.name}</h1>
        <p className="text-sm text-fg-muted">
          {fm(m.headline, {
            status: data.status,
            province: data.province || fm(m.none),
            created: formatDate(new Date(data.created_at), { locale, timeZone: zone }),
          })}
        </p>
      </div>
      {extra}
      <Section title={fm(m.subscription)}>
        {data.subscription ? (
          <p className="text-sm">
            {fm(m.ends, {
              status: data.subscription.status,
              package: data.subscription.package || fm(m.none),
              date: data.subscription.current_period_end
                ? formatDate(new Date(data.subscription.current_period_end), {
                    locale,
                    timeZone: zone,
                  })
                : fm(m.none),
            })}
            {data.subscription.package && canEditPackages ? (
              <>
                {" "}
                <Link
                  href={packageUrl(data.subscription.package)}
                  className="font-semibold text-fg-link underline"
                  data-package-link=""
                >
                  {fm(m.openPackage, { package: data.subscription.package })}
                </Link>
              </>
            ) : null}
          </p>
        ) : (
          <p className="text-sm text-fg-muted">{fm(m.noSubscription)}</p>
        )}
      </Section>
      <ProductGrants
        organisationId={data.id}
        canGrant={canEditPackages}
        timeZone={zone}
        onChanged={() => setAttempt((n) => n + 1)}
      />
      <Section title={fm(m.timeline)}>
        <ol className="flex flex-col gap-1 text-sm" data-timeline="">
          {data.timeline.map((item, index) => (
            <li key={`${item.at}-${index}`} data-kind={item.kind}>
              <time dateTime={item.at} className="me-2 text-fg-muted">
                {when(item.at)}
              </time>
              {line(item)}
            </li>
          ))}
        </ol>
      </Section>
      <Section title={fm(m.users)}>
        <ul className="flex flex-col gap-1 text-sm" data-users="">
          {data.users.map((user) => (
            <li key={user.id} className="flex flex-wrap items-center gap-2" data-user={user.id}>
              <span>
                {fm(m.userLine, {
                  name: user.name,
                  email: user.email,
                  role: user.role,
                  last: user.last_login ? when(user.last_login) : fm(m.none),
                })}
              </span>
              {canImpersonate ? (
                <Button size="sm" variant="ghost" onClick={() => setActingAs(user)}>
                  {fm(im.signInAs, { name: user.name })}
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      </Section>
      <Section title={fm(m.practices)}>
        <ul className="flex flex-col gap-1 text-sm">
          {data.practices.map((practice) => (
            <li key={practice.id}>
              {fm(m.practiceLine, {
                name: practice.name,
                role: practice.role,
                staff: practice.staff_count,
                active: String(practice.active),
              })}
            </li>
          ))}
        </ul>
      </Section>
      <Section title={fm(m.audit)}>
        {data.recent_events.length ? (
          <ul className="flex flex-col gap-1 text-sm" data-audit="">
            {data.recent_events.map((event, index) => (
              <li key={`${event.at}-${index}`}>
                <time dateTime={event.at} className="me-2 text-fg-muted">
                  {when(event.at)}
                </time>
                {fm(m.eventLine, {
                  actor: event.actor,
                  action: event.action,
                  record: event.record || fm(m.none),
                })}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-fg-muted">{fm(m.auditNone)}</p>
        )}
      </Section>
      {actingAs ? (
        <StartImpersonationDialog
          organisation={{ id: data.id, name: data.name }}
          user={actingAs}
          open
          onClose={() => setActingAs(null)}
        />
      ) : null}
    </div>
  );
}
