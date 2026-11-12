"use client";

import { Button, Drawer, Spinner, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { useFormatMessage } from "@/i18n";

import { isAuditError, recordHistory, type AuditEvent, type AuditViewer } from "./api";
import { DiffViewer } from "./DiffViewer";
import { m } from "./messages";
import { auditDateTime } from "./time";

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
      {children}
      <ol aria-label={fm(m.timeline)} className="flex flex-col gap-4" data-history="">
        {state.rows.map((event) => (
          <li key={event.id} className="flex flex-col gap-2 border-s-2 border-border ps-4">
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-semibold">{event.action_label}</span>
              <time dateTime={event.at} className="text-fg-muted" data-audit-time="">
                {auditDateTime(event.at, { locale, viewer: state.viewer })}
              </time>
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
