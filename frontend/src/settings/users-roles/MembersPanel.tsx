"use client";

import {
  Badge,
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  formatDate,
  IconButton,
  Input,
  LoadingRegion,
  Select,
  SkeletonTable,
  useToast,
  type SelectGroup,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";
import type { AppLocale } from "@/i18n/locales";

import {
  errorText,
  isOk,
  usersRolesApi,
  type AccessRequest,
  type Member,
  type PendingInvitation,
  type Role,
} from "./api";
import { m, orgRoleNames, xm } from "./messages";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function CloseIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2.5" fill="none" />
    </svg>
  );
}

/**
 * Users (A-03-T11): everyone who can work in the organisation — members and staff of serving
 * practices — with their role chips, giving and taking roles, and inviting a user (the A-02
 * invitation API). Pending invitations are listed under the people.
 */
export function MembersPanel({
  org,
  roles,
  canAssign,
  onChanged,
}: {
  org: string;
  roles: Role[];
  /** Hide the role buttons when the API said the user may not give roles. */
  canAssign: boolean;
  onChanged?: () => void;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const toast = useToast();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [invitations, setInvitations] = useState<PendingInvitation[]>([]);
  const [requests, setRequests] = useState<AccessRequest[]>([]);
  const [failed, setFailed] = useState(false);
  const [assignFor, setAssignFor] = useState<Member | null>(null);

  const load = useCallback(async () => {
    setFailed(false);
    const [people, pending, asked] = await Promise.all([
      usersRolesApi.members(org),
      usersRolesApi.invitations(org),
      canAssign ? usersRolesApi.accessRequests(org) : Promise.resolve(null),
    ]);
    setRequests(asked && isOk<AccessRequest[]>(asked) ? asked.body : []);
    if (!isOk<Member[]>(people)) {
      setFailed(true);
      return;
    }
    setMembers(people.body);
    setInvitations(isOk<PendingInvitation[]>(pending) ? pending.body : []);
  }, [org, canAssign]);

  useEffect(() => {
    void load();
  }, [load]);

  const closeRequest = async (request: AccessRequest) => {
    const result = await usersRolesApi.closeAccessRequest(org, request.id);
    if (result.status === 204) {
      toast.toast({ title: fm(xm.closed, { name: request.requester.name }) });
      await load();
    } else {
      toast.toast({ title: errorText(result.body) ?? fm(m.failed), tone: "danger" });
    }
  };

  const takeAway = async (member: Member, role: { id: string; name: string }) => {
    const result = await usersRolesApi.unassignRole(org, member.id, role.id);
    if (result.status === 204) {
      toast.toast({ title: fm(m.roleTaken, { role: role.name, name: member.name }) });
      await load();
      onChanged?.();
    } else {
      toast.toast({ title: errorText(result.body) ?? fm(m.failed), tone: "danger" });
    }
  };

  if (failed) {
    return (
      <ErrorState
        title={fm(m.loadFailed)}
        retryLabel={fm(m.retry)}
        onRetry={() => void load()}
        headingLevel={3}
      />
    );
  }
  if (members === null) {
    return (
      <LoadingRegion label={fm(m.loading)}>
        <SkeletonTable rows={4} columns={4} />
      </LoadingRegion>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{fm(m.usersHeading)}</h2>
        {canAssign ? (
          <InviteDialog
            org={org}
            roles={roles}
            onInvited={async (email) => {
              toast.toast({ title: fm(m.invited, { email }), tone: "success" });
              await load();
            }}
          />
        ) : null}
      </div>
      {requests.length ? (
        <section
          aria-labelledby="access-requests"
          className="flex flex-col gap-2 rounded-lg border-2 border-border bg-surface-warning-subtle p-4"
        >
          <h3 id="access-requests" className="text-base font-semibold">
            {fm(xm.requestsHeading)}
          </h3>
          <ul className="flex flex-col gap-3">
            {requests.map((request) => {
              const person = members.find((p) => p.id === request.requester.id);
              return (
                <li key={request.id} className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-sm">
                    <p className="font-semibold">
                      {fm(xm.requestRow, {
                        name: request.requester.name,
                        permission: request.permission.label,
                      })}
                    </p>
                    {request.note ? (
                      <p className="text-fg-muted">{fm(xm.requestNote, { note: request.note })}</p>
                    ) : null}
                  </div>
                  <span className="inline-flex gap-2">
                    {person ? (
                      <Button
                        size="sm"
                        variant="secondary"
                        aria-label={fm(m.giveRoleTo, { name: person.name })}
                        onClick={() => setAssignFor(person)}
                      >
                        {fm(m.giveRole)}
                      </Button>
                    ) : null}
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={fm(xm.close, { name: request.requester.name })}
                      onClick={() => void closeRequest(request)}
                    >
                      {fm(xm.closeShort)}
                    </Button>
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
      {members.length === 0 ? (
        <EmptyState title={fm(m.noUsers)} compact headingLevel={3} />
      ) : (
        <div className="relative overflow-x-auto rounded-lg border border-border">
          <table className="w-full border-collapse text-sm [overflow-wrap:anywhere]">
            <caption className="sr-only">{fm(m.usersTable)}</caption>
            <thead className="bg-surface-muted text-start text-xs font-semibold text-fg-muted">
              <tr>
                <th scope="col" className="px-3 py-2 text-start">
                  {fm(m.colName)}
                </th>
                <th scope="col" className="px-3 py-2 text-start">
                  {fm(m.colRoles)}
                </th>
                <th scope="col" className="px-3 py-2 text-start">
                  {fm(m.colAccess)}
                </th>
                {canAssign ? (
                  <th scope="col" className="px-3 py-2 text-end">
                    <span className="sr-only">{fm(m.colActions)}</span>
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {members.map((member) => (
                <tr key={member.id} className="border-t border-border align-top">
                  <th scope="row" className="px-3 py-3 text-start font-normal">
                    <span className="block font-semibold text-fg">{member.name}</span>
                    <span className="block text-fg-muted">{member.email}</span>
                  </th>
                  <td className="px-3 py-3">
                    <ul className="flex flex-wrap gap-1.5" aria-label={fm(m.colRoles)}>
                      {member.main_role ? (
                        <li>
                          <Badge tone="accent">
                            {fm(m.mainRole, { role: member.main_role.name })}
                          </Badge>
                        </li>
                      ) : null}
                      {member.practices.map((p) => (
                        <li key={p.id}>
                          <Badge tone="info">{p.role_name}</Badge>
                        </li>
                      ))}
                      {member.roles.map((role) => (
                        <li key={role.id} className="inline-flex items-center gap-0.5">
                          <Badge>{role.name}</Badge>
                          {canAssign ? (
                            <IconButton
                              size="sm"
                              label={fm(m.removeRole, { role: role.name, name: member.name })}
                              icon={<CloseIcon />}
                              onClick={() => void takeAway(member, role)}
                            />
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td className="px-3 py-3 text-fg-muted">
                    {member.kind === "member"
                      ? fm(m.accessMember)
                      : member.practices
                          .map((p) => fm(m.accessPractice, { practice: p.name, role: p.role_name }))
                          .join(" · ")}
                  </td>
                  {canAssign ? (
                    <td className="px-3 py-3 text-end">
                      <Button
                        size="sm"
                        variant="secondary"
                        aria-label={fm(m.giveRoleTo, { name: member.name })}
                        onClick={() => setAssignFor(member)}
                      >
                        {fm(m.giveRole)}
                      </Button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {invitations.length ? (
        <section aria-labelledby="pending-invitations" className="flex flex-col gap-2">
          <h3 id="pending-invitations" className="text-base font-semibold">
            {fm(m.pendingHeading)}
          </h3>
          <ul className="flex flex-col gap-1 text-sm text-fg-muted">
            {invitations.map((invitation) => (
              <li key={invitation.id}>
                {fm(m.pendingRow, {
                  email: invitation.email,
                  role: fm(orgRoleNames.role, { role: invitation.role }),
                  inviter: invitation.inviter_name,
                  expires: formatDate(new Date(invitation.expires_at), { locale }),
                })}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {assignFor ? (
        <AssignDialog
          org={org}
          member={assignFor}
          roles={roles}
          onClose={() => setAssignFor(null)}
          onAssigned={async (role) => {
            toast.toast({
              title: fm(m.roleGiven, { name: assignFor.name, role: role.name }),
              tone: "success",
            });
            setAssignFor(null);
            await load();
            onChanged?.();
          }}
        />
      ) : null}
    </div>
  );
}

function roleGroups(
  roles: Role[],
  member: Member | null,
  fm: ReturnType<typeof useFormatMessage>,
): SelectGroup[] {
  const assignable = roles.filter((r) => r.assignable);
  const held = new Set([member?.main_role?.id, ...(member?.roles ?? []).map((r) => r.id)]);
  const main = assignable.filter((r) => r.is_system && !held.has(r.id));
  const custom = assignable.filter((r) => !r.is_system && !held.has(r.id));
  const groups: SelectGroup[] = [];
  if (main.length && (member === null || member.kind === "member")) {
    groups.push({
      label: fm(m.groupMain),
      options: main.map((r) => ({ value: r.id, label: r.name })),
    });
  }
  if (custom.length && member !== null) {
    groups.push({
      label: fm(m.groupCustom),
      options: custom.map((r) => ({ value: r.id, label: r.name })),
    });
  }
  return groups;
}

function AssignDialog({
  org,
  member,
  roles,
  onClose,
  onAssigned,
}: {
  org: string;
  member: Member;
  roles: Role[];
  onClose: () => void;
  onAssigned: (role: Role) => Promise<void>;
}) {
  const fm = useFormatMessage();
  const labelId = useId();
  const errorId = useId();
  const [role, setRole] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const groups = roleGroups(roles, member, fm);

  const submit = async () => {
    const chosen = roles.find((r) => r.id === role);
    if (!chosen) {
      setError(fm(m.rolePlaceholder));
      return;
    }
    setBusy(true);
    const result = await usersRolesApi.assignRole(org, member.id, chosen.id);
    setBusy(false);
    if (isOk<Member>(result)) await onAssigned(chosen);
    else setError(errorText(result.body) ?? fm(m.failed));
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={fm(m.giveRoleTo, { name: member.name })}
      description={
        member.kind === "member"
          ? fm(m.giveRoleHelp)
          : fm(m.giveRolePracticeHelp, { name: member.name })
      }
      closeLabel={fm(m.close)}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {fm(m.cancel)}
          </Button>
          <Button loading={busy} onClick={() => void submit()}>
            {fm(m.give)}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-1.5">
        <span id={labelId} className="text-sm font-semibold">
          {fm(m.roleLabel)}
        </span>
        <Select
          options={groups}
          value={role}
          onValueChange={(value) => {
            setRole(value);
            setError(null);
          }}
          placeholder={fm(m.rolePlaceholder)}
          aria-labelledby={labelId}
          aria-describedby={error ? errorId : undefined}
          invalid={error !== null}
        />
        {error ? (
          <p id={errorId} role="alert" className="text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
      </div>
    </Dialog>
  );
}

function InviteDialog({
  org,
  roles,
  onInvited,
}: {
  org: string;
  roles: Role[];
  onInvited: (email: string) => Promise<void>;
}) {
  const fm = useFormatMessage();
  const emailId = useId();
  const roleLabelId = useId();
  const errorId = useId();
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("employee");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const mainRoles = roles.filter((r) => r.assignable && r.is_system);

  const submit = async () => {
    const address = email.trim();
    if (!EMAIL.test(address)) {
      setError(fm(m.emailInvalid));
      return;
    }
    setBusy(true);
    const result = await usersRolesApi.invite(org, address, role);
    setBusy(false);
    if (result.status === 201) {
      setOpen(false);
      setEmail("");
      await onInvited(address);
    } else {
      setError(errorText(result.body) ?? fm(m.failed));
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        setError(null);
      }}
      trigger={<Button>{fm(m.invite)}</Button>}
      title={fm(m.invite)}
      description={fm(m.inviteHelp)}
      closeLabel={fm(m.close)}
      footer={
        <>
          <Button variant="secondary" onClick={() => setOpen(false)}>
            {fm(m.cancel)}
          </Button>
          <Button loading={busy} onClick={() => void submit()}>
            {fm(m.sendInvite)}
          </Button>
        </>
      }
    >
      <form
        className="flex flex-col gap-4"
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <div className="flex flex-col gap-1.5">
          <label htmlFor={emailId} className="text-sm font-semibold">
            {fm(m.email)}
          </label>
          <Input
            id={emailId}
            type="email"
            autoComplete="off"
            value={email}
            invalid={error !== null}
            aria-describedby={error ? errorId : undefined}
            onChange={(event) => {
              setEmail(event.target.value);
              setError(null);
            }}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <span id={roleLabelId} className="text-sm font-semibold">
            {fm(m.roleLabel)}
          </span>
          <Select
            options={mainRoles.map((r) => ({ value: r.key, label: r.name }))}
            value={role}
            onValueChange={setRole}
            aria-labelledby={roleLabelId}
          />
        </div>
        {error ? (
          <p id={errorId} role="alert" className="text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
      </form>
    </Dialog>
  );
}
