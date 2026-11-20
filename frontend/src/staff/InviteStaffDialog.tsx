"use client";

/**
 * Invite a staff member (V-05-T03): email and practice role, sent through the A-02 invitation
 * flow (`practice_staff`). The link works once and for 14 days; the invitation shows as Pending in
 * the staff list until accepted.
 */
import { Button, Dialog, Input } from "@numo9/ui";
import { useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import {
  inviteErrorText,
  invitationsApi,
  PRACTICE_ROLES,
  type PracticeRole,
  type StaffInvitation,
} from "./invitations";
import { im } from "./inviteMessages";
import { m } from "./messages";

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** The translated name of a system practice role. */
export function practiceRoleLabel(role: string, fm: ReturnType<typeof useFormatMessage>): string {
  const labels: Record<PracticeRole, string> = {
    accountant: fm(m.roleAccountant),
    reviewer: fm(m.roleReviewer),
    payroll_specialist: fm(m.rolePayroll),
    practice_admin: fm(im.roleAdmin),
  };
  return labels[role as PracticeRole] ?? role;
}

export function InviteStaffDialog({
  practice,
  onInvited,
}: {
  practice: string;
  onInvited: (invitation: StaffInvitation) => void;
}) {
  const fm = useFormatMessage();
  const ids = { email: useId(), role: useId(), hint: useId(), error: useId() };
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<PracticeRole>("accountant");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const reset = () => {
    setEmail("");
    setRole("accountant");
    setError("");
  };

  const send = async () => {
    const address = email.trim();
    if (!EMAIL.test(address)) {
      setError(fm(im.emailInvalid));
      return;
    }
    setBusy(true);
    const result = await invitationsApi.invite(practice, address, role);
    setBusy(false);
    if (result.status === 201 && "id" in result.body) {
      onInvited(result.body as StaffInvitation);
      setOpen(false);
      reset();
      return;
    }
    setError(inviteErrorText(result.body) || fm(im.failed));
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
      trigger={<Button variant="primary">{fm(im.invite)}</Button>}
      title={fm(im.title)}
      description={fm(im.body)}
      closeLabel={fm(im.close)}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setOpen(false)}>
            {fm(im.cancel)}
          </Button>
          <Button variant="primary" loading={busy} onClick={() => void send()}>
            {fm(im.send)}
          </Button>
        </div>
      }
    >
      <form
        className="grid gap-3"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void send();
        }}
      >
        <div className="grid gap-1">
          <label htmlFor={ids.email} className="text-sm font-semibold text-fg">
            {fm(im.email)}
          </label>
          <Input
            id={ids.email}
            type="email"
            autoComplete="off"
            value={email}
            invalid={Boolean(error)}
            aria-describedby={error ? ids.error : undefined}
            onChange={(event) => {
              setEmail(event.target.value);
              setError("");
            }}
          />
        </div>
        <div className="grid gap-1">
          <label htmlFor={ids.role} className="text-sm font-semibold text-fg">
            {fm(im.role)}
          </label>
          <select
            id={ids.role}
            className="min-h-touch-target rounded-md border border-border-strong bg-surface px-2 text-sm"
            value={role}
            aria-describedby={ids.hint}
            onChange={(event) => setRole(event.target.value as PracticeRole)}
          >
            {PRACTICE_ROLES.map((value) => (
              <option key={value} value={value}>
                {practiceRoleLabel(value, fm)}
              </option>
            ))}
          </select>
          <p id={ids.hint} className="text-xs text-fg-muted">
            {fm(im.roleHint)}
          </p>
        </div>
        {error ? (
          <p id={ids.error} role="alert" className="text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
      </form>
    </Dialog>
  );
}

export function PendingInvitationActions({
  row,
  onResent,
  onRevoked,
  onError,
}: {
  row: { id: string; email: string };
  onResent: (invitation: StaffInvitation) => void;
  onRevoked: () => void;
  onError: (text: string) => void;
}) {
  const fm = useFormatMessage();
  const [busy, setBusy] = useState<"resend" | "revoke" | null>(null);
  const act = async (kind: "resend" | "revoke") => {
    setBusy(kind);
    const result = await invitationsApi[kind](row.id);
    setBusy(null);
    if (result.status === 200 && "id" in result.body) {
      if (kind === "resend") onResent(result.body as StaffInvitation);
      else onRevoked();
    } else onError(inviteErrorText(result.body) || fm(im.failed));
  };
  return (
    <span
      className="flex gap-1"
      onClick={(event) => event.stopPropagation()}
      onKeyDown={(event) => event.stopPropagation()}
    >
      <Button
        size="sm"
        variant="ghost"
        loading={busy === "resend"}
        aria-label={fm(im.resendLabel, { email: row.email })}
        onClick={() => void act("resend")}
      >
        {fm(im.resend)}
      </Button>
      <Button
        size="sm"
        variant="ghost"
        loading={busy === "revoke"}
        aria-label={fm(im.revokeLabel, { email: row.email })}
        onClick={() => void act("revoke")}
      >
        {fm(im.revoke)}
      </Button>
    </span>
  );
}
