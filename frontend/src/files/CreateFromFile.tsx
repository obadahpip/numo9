"use client";

import { Button, Spinner } from "@numo9/ui";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { filesApi, type FileAction } from "./api";
import { fm as m } from "./messages";

export interface CreateFromFileProps {
  org: string;
  documentId: string;
  /** Opens an available action (defaults to following its URL). */
  onOpen?: (action: FileAction) => void;
  /** Actions already loaded (tests, server render); otherwise fetched. */
  actions?: FileAction[];
}

/**
 * "Create from this file" (A-06-T11): every action modules register — a bill, an expense claim,
 * an asset — as a button. Actions that can't run yet stay visible, greyed, with the reason next to
 * them ("Bills arrive with Purchases in Phase 1."), linked by `aria-describedby` so screen readers
 * read why. Never hidden, never disabled without a reason.
 */
export function CreateFromFile({ org, documentId, onOpen, actions: given }: CreateFromFileProps) {
  const t = useFormatMessage();
  const headingId = useId();
  const [state, setState] = useState<
    { kind: "loading" } | { kind: "failed" } | { kind: "ready"; actions: FileAction[] }
  >(given ? { kind: "ready", actions: given } : { kind: "loading" });

  useEffect(() => {
    if (given) {
      setState({ kind: "ready", actions: given });
      return;
    }
    let live = true;
    setState({ kind: "loading" });
    void filesApi.actions(org, documentId).then((result) => {
      if (!live) return;
      if (result.status === 200 && Array.isArray(result.body.results)) {
        setState({ kind: "ready", actions: result.body.results });
      } else {
        setState({ kind: "failed" });
      }
    });
    return () => {
      live = false;
    };
  }, [org, documentId, given]);

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2">
      <h3 id={headingId} className="text-sm font-semibold text-fg">
        {t(m.createTitle)}
      </h3>
      {state.kind === "loading" && (
        <p className="flex items-center gap-2 text-sm text-fg-muted">
          <Spinner /> {t(m.createLoading)}
        </p>
      )}
      {state.kind === "failed" && <p className="text-sm text-fg-danger">{t(m.createFailed)}</p>}
      {state.kind === "ready" && state.actions.length === 0 && (
        <p className="text-sm text-fg-muted">{t(m.createNone)}</p>
      )}
      {state.kind === "ready" && state.actions.length > 0 && (
        <ul className="flex flex-col gap-2">
          {state.actions.map((action) => {
            const reasonId = `${headingId}-${action.key}-reason`;
            return (
              <li key={action.key} className="flex flex-col gap-1">
                <Button
                  size="sm"
                  variant={action.available ? "secondary" : "ghost"}
                  aria-disabled={!action.available || undefined}
                  aria-describedby={action.available ? undefined : reasonId}
                  onClick={() => {
                    if (!action.available) return;
                    if (onOpen) onOpen(action);
                    else if (action.url) window.location.assign(action.url);
                  }}
                  className="justify-start"
                >
                  {action.label}
                </Button>
                {!action.available && action.reason && (
                  <p id={reasonId} className="text-xs text-fg-muted">
                    {action.reason}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
