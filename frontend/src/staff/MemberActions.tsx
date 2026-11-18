"use client";

/**
 * Suspend / lift suspension / remove a staff member (V-05-T09 on the V-05-T05 service): suspend
 * keeps the history and blocks access; remove revokes every organisation. The server refuses the
 * last practice admin and its explanation is shown as is.
 */
import { Button, Dialog } from "@numo9/ui";
import { useState } from "react";

import type { ApiResult, Numo9Error } from "@/auth/client";
import { useFormatMessage } from "@/i18n";
import { practiceStaffUrl } from "@/routing/routes";

import { memberApi, type StaffMember } from "./api";
import { m } from "./messages";
import { StaffStatusBadge } from "./StaffStatusBadge";
import { staffStatus } from "./status";

function detail(result: ApiResult<unknown>): string | undefined {
  const body = result.body as Numo9Error | undefined;
  return typeof body?.detail === "string" ? body.detail : undefined;
}

export function MemberActions({
  practice,
  person,
  onChange,
}: {
  practice: string;
  person: StaffMember;
  onChange: (person: StaffMember) => void;
}) {
  const fm = useFormatMessage();
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const name = person.name || person.email;
  const status = staffStatus(person);

  const run = async (
    action: () => Promise<ApiResult<unknown>>,
    done: (result: ApiResult<unknown>) => void,
  ) => {
    setBusy(true);
    setError("");
    setNotice("");
    const result = await action();
    setBusy(false);
    if (result.status >= 200 && result.status < 300) done(result);
    else setError(detail(result) ?? fm(m.actionFailed));
  };

  return (
    <section className="flex flex-col gap-3" aria-label={fm(m.statusLine)}>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-fg-muted">{fm(m.statusLine)}</span>
        <StaffStatusBadge status={status} />
        {person.status === "suspended" ? (
          <Button
            size="sm"
            disabled={busy}
            onClick={() =>
              void run(
                () => memberApi.reinstate(practice, person.id),
                (result) => {
                  onChange(result.body as StaffMember);
                  setNotice(fm(m.reinstated, { name }));
                },
              )
            }
          >
            {fm(m.reinstateAction)}
          </Button>
        ) : (
          <Button
            size="sm"
            variant="danger"
            disabled={busy}
            onClick={() =>
              void run(
                () => memberApi.suspend(practice, person.id),
                (result) => {
                  onChange(result.body as StaffMember);
                  setNotice(fm(m.suspended, { name }));
                },
              )
            }
          >
            {fm(m.suspendAction)}
          </Button>
        )}
        <Dialog
          open={confirming}
          onOpenChange={setConfirming}
          title={fm(m.removeTitle, { name })}
          description={fm(m.removeBody)}
          closeLabel={fm(m.close)}
          size="sm"
          trigger={
            <Button size="sm" variant="danger" disabled={busy}>
              {fm(m.removeAction)}
            </Button>
          }
          footer={
            <>
              <Button onClick={() => setConfirming(false)}>{fm(m.cancel)}</Button>
              <Button
                variant="danger"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => memberApi.remove(practice, person.id),
                    () => {
                      setConfirming(false);
                      window.location.assign(practiceStaffUrl(practice));
                    },
                  ).then(() => setConfirming(false))
                }
              >
                {fm(m.removeAction)}
              </Button>
            </>
          }
        />
      </div>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <p role="status" className="text-sm text-fg-muted">
        {notice}
      </p>
    </section>
  );
}
