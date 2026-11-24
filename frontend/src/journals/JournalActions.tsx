"use client";

/**
 * The journal page's actions bar (C-04-T10): the buttons the state matrix (`actions.ts`) gives
 * for this journal and this person — Post / Submit for approval (draft), Approve / Send back (an
 * approver), Withdraw (the author), Copy, Reverse (posted). Send back asks for a reason; Reverse
 * asks for the reversal's date. A refusal is shown under the bar in the server's words.
 */
import { Button, Dialog, Input } from "@numo9/ui";
import Link from "next/link";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";
import { myPermissions } from "@/search/api";

import { journalActions, type JournalAction } from "./actions";
import type { Journal } from "./api";
import { am } from "./actionMessages";
import { writeApi } from "./write/api";

const MIN_REASON = 3;

export interface JournalActionsProps {
  org: string;
  journal: Journal;
  /** After an action: the journal it produced (the same one, or the reversal). */
  onDone: (journal: Journal) => void;
}

export function JournalActions({ org, journal, onDone }: Readonly<JournalActionsProps>) {
  const fm = useFormatMessage();
  const ids = useId();
  const [canWrite, setCanWrite] = useState(false);
  const [busy, setBusy] = useState<JournalAction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<"reject" | "reverse" | null>(null);
  const [reason, setReason] = useState("");
  const [date, setDate] = useState(journal.date);

  useEffect(() => {
    myPermissions(org)
      .then((keys) => setCanWrite(keys === null || keys.has("accounting.journals.post")))
      .catch(() => setCanWrite(false));
  }, [org]);

  const actions = journalActions({
    status: journal.status,
    manual: journal.type === "manual",
    canWrite,
    isAuthor: journal.viewer?.is_author,
    canApprove: journal.viewer?.can_approve,
  });

  const run = async (
    action: "post" | "submit" | "approve" | "reject" | "withdraw" | "reverse",
    body: Record<string, unknown> = {},
  ) => {
    setBusy(action);
    setError(null);
    const result = await writeApi.action(org, journal.id, action, body).catch(() => null);
    setBusy(null);
    if (result && (result.status === 200 || result.status === 201)) {
      setDialog(null);
      onDone(result.body);
      return;
    }
    const refusal = result?.body as { detail?: string; errors?: { message: string }[] } | undefined;
    setError(refusal?.errors?.[0]?.message ?? refusal?.detail ?? fm(am.failed));
  };

  if (actions.length === 0) return null;
  const label: Record<JournalAction, string> = {
    saveDraft: fm(am.saveDraft),
    submit: fm(am.submit),
    post: fm(am.post),
    approve: fm(am.approve),
    reject: fm(am.reject),
    withdraw: fm(am.withdraw),
    copy: fm(am.copy),
    reverse: fm(am.reverse),
  };

  return (
    <div className="flex flex-col gap-2" data-journal-actions="">
      <div role="toolbar" aria-label={fm(am.toolbar)} className="flex flex-wrap gap-2">
        {actions.map((action, index) => {
          if (action === "copy")
            return (
              <Link
                key={action}
                href={`/o/${org}/accounting/journals/new?copy=${encodeURIComponent(journal.id)}`}
                className="inline-flex min-h-touch-target items-center rounded-md border border-border px-4 text-sm font-semibold text-fg"
                data-action={action}
              >
                {label.copy}
              </Link>
            );
          const onClick =
            action === "reject" || action === "reverse"
              ? () => setDialog(action)
              : () => void run(action as "post" | "submit" | "approve" | "withdraw");
          return (
            <Button
              key={action}
              variant={index === 0 ? "primary" : "secondary"}
              disabled={busy !== null}
              onClick={onClick}
              data-action={action}
            >
              {busy === action ? fm(am.working) : label[action]}
            </Button>
          );
        })}
      </div>
      {journal.viewer?.blocked === "self" && journal.status === "awaiting_approval" ? (
        <p className="text-sm text-fg-muted" data-self="">
          {fm(am.youCreated)}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <Dialog
        open={dialog === "reject"}
        onOpenChange={(open) => setDialog(open ? "reject" : null)}
        title={fm(am.rejectTitle)}
        closeLabel={fm(am.close)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDialog(null)}>
              {fm(am.cancel)}
            </Button>
            <Button
              disabled={busy !== null || reason.trim().length < MIN_REASON}
              onClick={() => void run("reject", { reason: reason.trim() })}
            >
              {fm(am.reject)}
            </Button>
          </>
        }
      >
        <label htmlFor={`${ids}-reason`} className="text-sm font-medium text-fg">
          {fm(am.reason, { min: MIN_REASON })}
        </label>
        <textarea
          id={`${ids}-reason`}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md border border-border bg-surface p-2 text-sm text-fg"
        />
      </Dialog>
      <Dialog
        open={dialog === "reverse"}
        onOpenChange={(open) => setDialog(open ? "reverse" : null)}
        title={fm(am.reverseTitle)}
        description={fm(am.reverseBody)}
        closeLabel={fm(am.close)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDialog(null)}>
              {fm(am.cancel)}
            </Button>
            <Button disabled={busy !== null || !date} onClick={() => void run("reverse", { date })}>
              {fm(am.reverse)}
            </Button>
          </>
        }
      >
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(am.reverseDate)}
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
      </Dialog>
    </div>
  );
}
