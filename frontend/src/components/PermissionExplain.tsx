"use client";

import { Button, ExplainPanel, Input } from "@numo9/ui";
import { useId, useState } from "react";

import { useFormatMessage } from "@/i18n";
import {
  errorText,
  isOk,
  usersRolesApi,
  type AccessRequest,
  type ApiError,
} from "@/settings/users-roles/api";
import { xm } from "@/settings/users-roles/messages";

/**
 * "Why can't I?" (A-03-T14): the ExplainPanel for a `403 permission.denied` answer — what is
 * refused (the API's own sentence), the permission it needs, who has it here, who could give
 * it, and **Request access** (emails those people; A-07 adds the notification centre). Any
 * screen that gets a refusal passes the error body.
 */
export function PermissionExplain({
  org,
  error,
  headingLevel = 2,
}: {
  org: string;
  error: ApiError;
  headingLevel?: 1 | 2;
}) {
  const fm = useFormatMessage();
  const noteId = useId();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ tone: "ok" | "error"; text: string } | null>(null);
  const explain = error.explain;

  const body = (
    <>
      <p>{errorText(error)}</p>
      {explain ? (
        <p className="mt-2">
          {fm(xm.needs, {
            permission: explain.permission.label,
            module: explain.permission.module_label,
            risk: explain.permission.risk_label.toLocaleLowerCase(),
          })}
        </p>
      ) : null}
      {explain ? (
        <p className="mt-2">
          {explain.holders.length
            ? fm(explain.holders_total > explain.holders.length ? xm.holdersMore : xm.holders, {
                names: explain.holders
                  .map((h) =>
                    h.roles.length
                      ? fm(xm.holder, { name: h.name, roles: h.roles.join(", ") })
                      : h.name,
                  )
                  .join(", "),
                more: explain.holders_total - explain.holders.length,
              })
            : fm(xm.nobodyHolds)}
        </p>
      ) : null}
    </>
  );

  const fixer = explain
    ? explain.managers.length
      ? fm(xm.fixer, { names: explain.managers.map((m) => m.name).join(", ") })
      : fm(xm.fixerNobody)
    : undefined;

  const request = async () => {
    if (!explain) return;
    setBusy(true);
    const answer = await usersRolesApi.requestAccess(org, explain.permission.key, note.trim());
    setBusy(false);
    if (isOk<AccessRequest>(answer)) {
      setResult({
        tone: "ok",
        text: answer.body.already_open
          ? fm(xm.alreadyOpen)
          : fm(xm.sent, { count: answer.body.notified }),
      });
    } else {
      setResult({ tone: "error", text: errorText(answer.body) ?? "" });
    }
  };

  const canRequest = explain?.can_request === true && result?.tone !== "ok";

  return (
    <ExplainPanel
      kind="permission"
      title={fm(xm.title)}
      headingLevel={headingLevel}
      body={body}
      fixer={fixer}
      actions={
        canRequest
          ? [
              <Button key="request" loading={busy} onClick={() => void request()}>
                {fm(xm.request)}
              </Button>,
            ]
          : []
      }
    >
      {canRequest ? (
        <div className="flex flex-col gap-1.5">
          <label htmlFor={noteId} className="text-sm font-semibold">
            {fm(xm.note)}
          </label>
          <Input
            id={noteId}
            value={note}
            maxLength={500}
            onChange={(event) => setNote(event.target.value)}
          />
        </div>
      ) : null}
      {result ? (
        <p
          role={result.tone === "ok" ? "status" : "alert"}
          className={`rounded-md border-2 px-4 py-3 text-sm ${
            result.tone === "ok"
              ? "border-border bg-surface-success-subtle"
              : "border-border-danger bg-surface-danger-subtle"
          }`}
        >
          {result.text}
        </p>
      ) : null}
    </ExplainPanel>
  );
}
