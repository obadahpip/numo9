"use client";

import {
  Button,
  DatePicker,
  Drawer,
  formatDate,
  Spinner,
  todayIn,
  type AppLocale,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useId, useState, type ReactNode } from "react";

import { useFormatMessage } from "@/i18n";

import {
  isAuditError,
  recordAsOf,
  recordHistory,
  type AuditAsOf,
  type AuditEvent,
  type AuditViewer,
} from "./api";
import { DiffViewer, useValueText } from "./DiffViewer";
import { m } from "./messages";
import { AuditTime } from "./time";

export interface RecordHistoryProps {
  org: string;
  /** Record type: the model label, e.g. `contacts.Contact`, `ledger.Account`, `rbac.Role`. */
  type: string;
  /** The record's public id. */
  id: string;
  /** The record's name, for the drawer title. */
  label: string;
  /** Extra content under the timeline's header (A-04-T11 "View as of date"). */
  children?: ReactNode;
}

type Loaded =
  | { kind: "loading" }
  | { kind: "ready"; rows: AuditEvent[]; next: string | null; viewer: AuditViewer }
  | { kind: "empty" }
  | { kind: "failed"; detail?: string };

/**
 * Record history (A-04-T10): the **History** button every detail page puts next to its heading,
 * and the drawer it opens — the record's changes over every date, newest first, each with who,
 * when (the viewer's 12/24-hour preference) and the DiffViewer; "Show older changes" pages back;
 * "Open in the audit log" opens the global viewer filtered to the record.
 *
 *     <RecordHistory org={org} type="contacts.Contact" id={contact.id} label={contact.name} />
 */
export function RecordHistory({ org, type, id, label, children }: Readonly<RecordHistoryProps>) {
  const fm = useFormatMessage();
  const [open, setOpen] = useState(false);
  return (
    <Drawer
      open={open}
      onOpenChange={setOpen}
      trigger={
        <Button variant="secondary" size="sm" data-record-history={type}>
          {fm(m.history)}
        </Button>
      }
      title={fm(m.historyOf, { record: label })}
      closeLabel={fm(m.close)}
      size="lg"
    >
      {open ? (
        <Timeline org={org} type={type} id={id}>
          {children}
        </Timeline>
      ) : null}
    </Drawer>
  );
}

function Timeline({
  org,
  type,
  id,
  children,
}: Readonly<{ org: string; type: string; id: string; children?: ReactNode }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [state, setState] = useState<Loaded>({ kind: "loading" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (cursor: string | null, before: AuditEvent[]) => {
      const answer = await recordHistory(org, type, id, cursor);
      if (answer.status === 404 && !cursor) return setState({ kind: "empty" });
      if (answer.status !== 200 || isAuditError(answer.body)) {
        const detail = isAuditError(answer.body) ? answer.body.detail : undefined;
        return setState({ kind: "failed", detail });
      }
      const page = answer.body;
      setState({
        kind: "ready",
        rows: [...before, ...page.results],
        next: page.next,
        viewer: page.viewer,
      });
    },
    [org, type, id],
  );

  useEffect(() => {
    void load(null, []);
  }, [load]);

  if (state.kind === "loading") {
    return (
      <p role="status" className="flex items-center gap-2 py-8 text-fg-muted">
        <Spinner />
        {fm(m.historyLoading)}
      </p>
    );
  }
  if (state.kind === "empty") return <p className="text-fg-muted">{fm(m.historyEmpty)}</p>;
  if (state.kind === "failed") {
    return (
      <p role="alert" className="text-fg-danger">
        {state.detail ?? fm(m.historyFailed)}
      </p>
    );
  }
  const params = new URLSearchParams({ object_type: type, object_id: id, from: "2000-01-01" });
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link
          href={`/o/${org}/settings/audit-log?${params.toString()}`}
          className="text-sm font-semibold underline underline-offset-2"
        >
          {fm(m.openLog)}
        </Link>
      </div>
      <AsOfPanel org={org} type={type} id={id} timeZone={state.viewer.time_zone} />
      {children}
      <ol aria-label={fm(m.timeline)} className="flex flex-col gap-4" data-history="">
        {state.rows.map((event) => (
          <li key={event.id} className="flex flex-col gap-2 border-s-2 border-border ps-4">
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-semibold">{event.action_label}</span>
              <AuditTime
                at={event.at}
                locale={locale}
                viewer={state.viewer}
                className="text-fg-muted"
              />
            </div>
            <span className="text-fg-muted">{event.actor.label}</span>
            {event.changes.length > 0 ? <DiffViewer changes={event.changes} /> : null}
          </li>
        ))}
      </ol>
      {state.next ? (
        <Button
          variant="secondary"
          loading={busy}
          onClick={async () => {
            setBusy(true);
            await load(state.next, state.rows);
            setBusy(false);
          }}
        >
          {fm(m.historyMore)}
        </Button>
      ) : null}
    </div>
  );
}

/**
 * "View as of" (A-04-T11): the record's fields at the end of a chosen day (organisation time),
 * rebuilt from its history by the API.
 */
function AsOfPanel({
  org,
  type,
  id,
  timeZone,
}: Readonly<{ org: string; type: string; id: string; timeZone: string }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const text = useValueText();
  const inputId = useId();
  const headingId = useId();
  const today = todayIn(timeZone);
  const [date, setDate] = useState<string | null>(null);
  const [result, setResult] = useState<AuditAsOf | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const show = async () => {
    if (!date) return;
    setBusy(true);
    const answer = await recordAsOf(org, type, id, date);
    setBusy(false);
    if (answer.status !== 200 || isAuditError(answer.body)) {
      setResult(null);
      setFailed(true);
      return;
    }
    setFailed(false);
    setResult(answer.body);
  };
  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-3 rounded-md bg-surface-muted p-3"
    >
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void show();
        }}
      >
        <div className="flex flex-col gap-1">
          <label htmlFor={inputId} className="font-medium">
            {fm(m.asOf)}
          </label>
          <DatePicker
            id={inputId}
            value={date}
            onChange={setDate}
            locale={locale}
            today={today}
            max={today}
            shortcuts={[]}
            labels={{
              openCalendar: fm(m.openCalendar),
              previousMonth: fm(m.previousMonth),
              nextMonth: fm(m.nextMonth),
              unreadable: fm(m.unreadable),
              shortcuts: {
                today: "",
                plus7: "",
                plus14: "",
                plus30: "",
                endOfMonth: "",
                endOfNextMonth: "",
              },
            }}
          />
        </div>
        <Button type="submit" size="sm" variant="secondary" loading={busy} disabled={!date}>
          {fm(m.asOfShow)}
        </Button>
      </form>
      <h3 id={headingId} className={result ? "font-semibold" : "sr-only"}>
        {result && date
          ? fm(m.asOfTitle, { record: result.record.label, date: formatDate(date, { locale }) })
          : fm(m.asOf)}
      </h3>
      {failed ? (
        <p role="alert" className="text-fg-danger">
          {fm(m.asOfFailed)}
        </p>
      ) : null}
      {result ? (
        <div className="flex flex-col gap-2" data-as-of="">
          {result.events_applied === 0 ? <p>{fm(m.asOfMissing)}</p> : null}
          {result.deleted ? <p>{fm(m.asOfDeleted)}</p> : null}
          {result.events_applied > 0 && !result.complete ? (
            <p className="text-fg-muted">{fm(m.asOfPartial)}</p>
          ) : null}
          {result.state.length > 0 ? (
            <dl
              aria-label={fm(m.asOfFields)}
              className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-[10rem_1fr]"
            >
              {result.state.map((row) => (
                <div key={row.field} className="contents" data-as-of-field={row.field}>
                  <dt className="font-medium">{row.label}</dt>
                  <dd className="break-all">{row.masked ? fm(m.hidden) : text(row.value)}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
