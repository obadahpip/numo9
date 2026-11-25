"use client";

/**
 * Tax settings history drawer (G-06-T08, wireframe 52 marker 9): every change to a tax object
 * (settings, registrations, codes, components) — who (a person, or a job with its id, never
 * just "System"), when, old → new, and the reason. One list: `GET audit/events?scope=tax`.
 */
import { Button, Drawer, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { apiRequest } from "@/auth/client";
import { auditApi, type AuditEvent, type AuditPage } from "@/audit/api";
import { DiffViewer } from "@/audit/DiffViewer";
import { AuditTime } from "@/audit/time";
import { useFormatMessage } from "@/i18n";

import { sm } from "./messages";

type Loaded = { kind: "loading" } | { kind: "failed" } | { kind: "ready"; page: AuditPage };

function who(event: AuditEvent, job: (name: string, id: string) => string): string {
  if (event.actor.user) return event.actor.user.name || event.actor.label;
  const run = (event.meta.job ?? null) as { id?: string; task?: string } | null;
  return run?.id ? job(event.actor.label || run.task || "", run.id.slice(0, 8)) : event.actor.label;
}

export function TaxHistory({ org }: Readonly<{ org: string }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<Loaded>({ kind: "loading" });

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setState({ kind: "loading" });
    void apiRequest<AuditPage>(`${auditApi(org, "events")}?scope=tax`).then((answer) => {
      if (cancelled) return;
      if (answer.status === 200 && Array.isArray(answer.body?.results)) {
        setState({ kind: "ready", page: answer.body });
      } else setState({ kind: "failed" });
    });
    return () => {
      cancelled = true;
    };
  }, [open, org]);

  return (
    <Drawer
      open={open}
      onOpenChange={setOpen}
      trigger={
        <Button variant="secondary" size="sm" data-tax-history="">
          {fm(sm.history)}
        </Button>
      }
      title={fm(sm.historyTitle)}
      closeLabel={fm(sm.close)}
      size="lg"
    >
      {state.kind === "failed" ? (
        <p role="alert" className="text-sm text-fg-danger">
          {fm(sm.historyFailed)}
        </p>
      ) : state.kind === "ready" && state.page.results.length === 0 ? (
        <p className="text-sm text-fg-muted">{fm(sm.historyEmpty)}</p>
      ) : state.kind === "ready" ? (
        <ol className="flex flex-col gap-4" data-tax-history-list="">
          {state.page.results.map((event) => {
            const reason = typeof event.meta.reason === "string" ? event.meta.reason : "";
            return (
              <li key={event.id} className="border-b border-border pb-3 text-sm text-fg">
                <p className="font-medium">
                  {fm(sm.historyWhat, { action: event.action_label, record: event.record.label })}
                </p>
                <p className="flex flex-wrap gap-x-2 text-fg-muted">
                  <span data-who="">
                    {who(event, (name, id) => fm(sm.historyJob, { name, id }))}
                  </span>
                  <AuditTime at={event.at} locale={locale} viewer={state.page.viewer} />
                </p>
                {event.changes.length ? (
                  <DiffViewer changes={event.changes} className="mt-1" />
                ) : null}
                {reason ? <p className="mt-1">{fm(sm.historyReason, { reason })}</p> : null}
              </li>
            );
          })}
        </ol>
      ) : null}
    </Drawer>
  );
}
