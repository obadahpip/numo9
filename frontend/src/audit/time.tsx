/**
 * Times in the audit log (A-04-T12): the viewer's own 12 h / 24 h preference (A-02-T01
 * `time_format`, sent by the API as `viewer`), their language and the organisation's time zone —
 * `26 Oct 2026, 4:33 p.m.` / `26 Oct 2026, 16:33` / `26 oct. 2026, 16 h 33`. Never "16:33PM"
 * (gap-44): the hour cycle and the day period always come from one formatter.
 */
import { formatDateTime, formatTime, type AppLocale } from "@numo9/ui";

import type { AuditViewer } from "./api";

export interface AuditTimeOptions {
  locale: AppLocale;
  viewer?: Pick<AuditViewer, "time_format" | "time_zone"> | null;
}

export function auditDateTime(at: string, { locale, viewer }: AuditTimeOptions): string {
  return formatDateTime(at, {
    locale,
    timeFormat: viewer?.time_format,
    timeZone: viewer?.time_zone,
  });
}

export function auditTime(at: string, { locale, viewer }: AuditTimeOptions): string {
  return formatTime(at, { locale, timeFormat: viewer?.time_format, timeZone: viewer?.time_zone });
}

/** A `<time>` element showing an audit timestamp the viewer's way (machine value: ISO). */
export function AuditTime({
  at,
  locale,
  viewer,
  className,
}: Readonly<{ at: string; className?: string } & AuditTimeOptions>) {
  return (
    <time dateTime={at} className={className} data-audit-time="">
      {auditDateTime(at, { locale, viewer })}
    </time>
  );
}
