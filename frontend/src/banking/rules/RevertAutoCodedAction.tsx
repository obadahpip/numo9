"use client";

/**
 * "Revert" on an auto-coded statement line (F-04-T15) — a self-contained action for the
 * statement-lines list (F-02): shown on lines a rule coded without review; asks once ("The
 * journal is reversed and the line goes back to Uncoded"), then calls the revert endpoint and
 * hands the result to ``onReverted``. Errors (a locked period, …) are shown in place.
 *
 *     <RevertAutoCodedAction org={org} line={line} onReverted={reload} />
 */
import { Button } from "@numo9/ui";
import { useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import { rulesApi, type RevertResult } from "./api";

const messages = defineMessages({
  revert: {
    id: "bankRules.revert.action",
    defaultMessage: "Revert auto-coding",
    description: "Action on an auto-coded statement line",
  },
  confirm: {
    id: "bankRules.revert.confirm",
    defaultMessage:
      "Revert the coding by {rule}? The journal is reversed and the line goes back to Uncoded.",
    description: "Confirmation before reverting",
  },
  confirmUnnamed: {
    id: "bankRules.revert.confirmUnnamed",
    defaultMessage:
      "Revert this coding? The journal is reversed and the line goes back to Uncoded.",
    description: "Confirmation before reverting (rule name unknown)",
  },
  yes: { id: "bankRules.revert.yes", defaultMessage: "Revert", description: "Confirm button" },
  no: { id: "bankRules.revert.no", defaultMessage: "Keep it", description: "Cancel button" },
  done: {
    id: "bankRules.revert.done",
    defaultMessage: "Reverted: the line is uncoded again.",
    description: "Status after reverting",
  },
  failed: {
    id: "bankRules.revert.failed",
    defaultMessage: "The coding couldn't be reverted.",
    description: "Error",
  },
});

export interface RevertableLine {
  id: string;
  auto_coded: boolean;
  applied_rule?: { id: string; name: string } | null;
}

export interface RevertAutoCodedActionProps {
  org: string;
  line: RevertableLine;
  onReverted?: (result: RevertResult) => void;
}

export function RevertAutoCodedAction({ org, line, onReverted }: RevertAutoCodedActionProps) {
  const fm = useFormatMessage();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  if (!line.auto_coded && !message) return null;

  async function revert() {
    setBusy(true);
    const result = await rulesApi.revertLine(org, line.id).catch(() => null);
    setBusy(false);
    setAsking(false);
    if (result?.status === 200) {
      setMessage({ text: fm(messages.done), error: false });
      onReverted?.(result.body);
    } else {
      const detail = result && typeof result.body === "object" ? result.body?.detail : undefined;
      setMessage({ text: detail || fm(messages.failed), error: true });
    }
  }

  return (
    <div className="flex flex-col gap-2" data-action="revert-auto-coding">
      {message ? (
        <p
          role={message.error ? "alert" : "status"}
          className={`text-sm ${message.error ? "font-semibold text-fg-danger" : "text-fg"}`}
        >
          {message.text}
        </p>
      ) : null}
      {line.auto_coded && !(message && !message.error) ? (
        asking ? (
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm text-fg">
              {line.applied_rule
                ? fm(messages.confirm, { rule: line.applied_rule.name })
                : fm(messages.confirmUnnamed)}
            </p>
            <Button variant="danger" size="sm" disabled={busy} onClick={() => void revert()}>
              {fm(messages.yes)}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setAsking(false)}>
              {fm(messages.no)}
            </Button>
          </div>
        ) : (
          <div>
            <Button variant="secondary" size="sm" onClick={() => setAsking(true)}>
              {fm(messages.revert)}
            </Button>
          </div>
        )
      ) : null}
    </div>
  );
}
