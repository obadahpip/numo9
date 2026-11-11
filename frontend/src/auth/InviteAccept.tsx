"use client";

import { BUTTON_BASE, Button, formatDate, Select, Skeleton } from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState } from "react";

import { defineMessages, useFormatMessage, type FormatMessage } from "@/i18n";
import type { AppLocale } from "@/i18n/locales";
import { loadMyOrganisations, resetMyOrganisations } from "@/org/myOrganisations";
import { orgModuleUrl } from "@/routing/routes";

import {
  apiRequest,
  authRequest,
  isAuthenticated,
  resetCsrfToken,
  type Numo9Error,
} from "./client";
import { authMessages, requestFailureMessage } from "./messages";
import { Notice } from "./Notice";

const messages = defineMessages({
  loading: {
    id: "auth.invite.loading",
    defaultMessage: "Opening your invitation…",
    description: "Invitation page while the link is checked",
  },
  title: {
    id: "auth.invite.title",
    defaultMessage: "You're invited to {target}",
    description: "Invitation heading; {target} is the practice or organisation",
  },
  practiceStaff: {
    id: "auth.invite.practiceStaff",
    defaultMessage: "{inviter} invited you to join the practice {target} as {role}.",
    description: "Invitation body: practice staff",
  },
  organisationOwner: {
    id: "auth.invite.organisationOwner",
    defaultMessage:
      "{inviter} invited you to become the owner of {target} on Numo9. Your accountant stays connected to the organisation.",
    description: "Invitation body: practice invites the organisation's owner",
  },
  organisationUser: {
    id: "auth.invite.organisationUser",
    defaultMessage: "{inviter} invited you to join {target} as {role}.",
    description: "Invitation body: organisation invites a user",
  },
  organisationAccountant: {
    id: "auth.invite.organisationAccountant",
    defaultMessage: "{inviter} invited you and your practice to look after {target} ({role}).",
    description: "Invitation body: organisation invites its accountant",
  },
  role: {
    id: "auth.invite.role",
    defaultMessage:
      "{role, select, practice_admin {Practice admin} accountant {Accountant} reviewer {Reviewer} payroll_specialist {Payroll specialist} read_only {Read-only staff} owner {Owner} admin {Admin} accountant_delegate {Accountant delegate} sales {Sales} purchasing {Purchasing} payroll {Payroll} hr {HR} employee {Employee} full_service {full service} bookkeeping {bookkeeping} tax {tax} other {{role}}}",
    description:
      "Role or service named in an invitation (practice, organisation and assignment roles)",
  },
  forEmail: {
    id: "auth.invite.forEmail",
    defaultMessage: "Invitation for {email} · expires {expires}",
    description: "Invitation details line",
  },
  signInToAccept: {
    id: "auth.invite.signInToAccept",
    defaultMessage: "Sign in to accept",
    description: "Button: sign in, then come back to accept",
  },
  newHere: {
    id: "auth.invite.newHere",
    defaultMessage:
      "New to Numo9? Create your account with {email}, verify it, then open this invitation link again.",
    description: "Invitation: instructions for someone without an account",
  },
  accept: {
    id: "auth.invite.accept",
    defaultMessage: "Accept invitation",
    description: "Button: accept",
  },
  signedInAs: {
    id: "auth.invite.signedInAs",
    defaultMessage: "You're signed in as {email}.",
    description: "Invitation: the current account",
  },
  wrongTitle: {
    id: "auth.invite.wrongTitle",
    defaultMessage: "This invitation is for another account",
    description: "Invitation opened while signed in as someone else: heading",
  },
  wrongBody: {
    id: "auth.invite.wrongBody",
    defaultMessage:
      "It was sent to {invited}, but you're signed in as {current}. Sign out, then sign in or create an account with {invited}.",
    description: "Invitation opened while signed in as someone else: explanation",
  },
  switchAccount: {
    id: "auth.invite.switchAccount",
    defaultMessage: "Sign out and continue",
    description: "Button: sign out of the current account and continue with the invitation",
  },
  keepAccount: {
    id: "auth.invite.keepAccount",
    defaultMessage: "Stay signed in and go to Home",
    description: "Link: ignore the invitation for now",
  },
  invalidTitle: {
    id: "auth.invite.invalidTitle",
    defaultMessage: "This invitation link doesn't work",
    description: "Invitation: invalid link heading",
  },
  usedTitle: {
    id: "auth.invite.usedTitle",
    defaultMessage: "This invitation has already been accepted",
    description: "Invitation: used link heading",
  },
  revokedTitle: {
    id: "auth.invite.revokedTitle",
    defaultMessage: "This invitation was withdrawn",
    description: "Invitation: revoked link heading",
  },
  expiredTitle: {
    id: "auth.invite.expiredTitle",
    defaultMessage: "This invitation has expired",
    description: "Invitation: expired link heading",
  },
  goHome: { id: "auth.invite.goHome", defaultMessage: "Go to Home", description: "Link to /" },
  choosePractice: {
    id: "auth.invite.choosePractice",
    defaultMessage: "Practice that will serve this client",
    description: "Select label: accountant in several practices picks one",
  },
  choosePlaceholder: {
    id: "auth.invite.choosePlaceholder",
    defaultMessage: "Choose a practice",
    description: "Placeholder of the practice select",
  },
  chooseFirst: {
    id: "auth.invite.chooseFirst",
    defaultMessage: "Choose the practice first.",
    description: "Validation: no practice chosen",
  },
  doneTitle: {
    id: "auth.invite.doneTitle",
    defaultMessage: "You've joined {target}",
    description: "Invitation accepted: heading",
  },
  doneBody: {
    id: "auth.invite.doneBody",
    defaultMessage:
      "{inviter} can see that you accepted. Everything you can do depends on your role ({role}).",
    description: "Invitation accepted: body",
  },
  open: {
    id: "auth.invite.open",
    defaultMessage: "Open {target}",
    description: "Link after accepting: open the organisation or practice",
  },
});

/** `POST /api/v1/invitations/preview` answer (InvitationSerializer). */
interface Invitation {
  id: string;
  kind: "practice_staff" | "organisation_owner" | "organisation_user" | "organisation_accountant";
  email: string;
  role: string;
  status: string;
  expires_at: string;
  target_name: string;
  target_id: string;
  inviter_name: string;
}

type Dead = "invalid" | "used" | "revoked" | "expired";

type State =
  | { kind: "loading" }
  | { kind: "dead"; reason: Dead; detail?: string }
  | { kind: "failed"; message: string }
  | { kind: "ready"; invitation: Invitation; account: string | null }
  | { kind: "done"; invitation: Invitation };

const DEAD_CODES: Record<string, Dead> = {
  "invitation.invalid": "invalid",
  "invitation.used": "used",
  "invitation.revoked": "revoked",
  "invitation.expired": "expired",
};

function deadReason(status: number, body: Numo9Error): Dead | undefined {
  const byCode = body.code ? DEAD_CODES[body.code] : undefined;
  if (byCode) return byCode;
  if (status === 404) return "invalid";
  return undefined;
}

function sameEmail(a: string | null | undefined, b: string | null | undefined): boolean {
  return Boolean(a && b && a.trim().toLowerCase() === b.trim().toLowerCase());
}

function body(fm: FormatMessage, invitation: Invitation): string {
  const values = {
    inviter: invitation.inviter_name,
    target: invitation.target_name,
    role: fm(messages.role, { role: invitation.role }),
  };
  switch (invitation.kind) {
    case "practice_staff":
      return fm(messages.practiceStaff, values);
    case "organisation_owner":
      return fm(messages.organisationOwner, values);
    case "organisation_accountant":
      return fm(messages.organisationAccountant, values);
    default:
      return fm(messages.organisationUser, values);
  }
}

/** Where the accepted invitation leads: the organisation's Home, or Home for a practice. */
function destination(invitation: Invitation): string {
  return invitation.kind === "practice_staff" ? "/" : orgModuleUrl(invitation.target_id, "home");
}

const PRIMARY_LINK = `${BUTTON_BASE} min-h-touch-target w-full bg-surface-accent px-4 text-sm text-fg-on-accent hover:bg-surface-accent-hover`;
const SECONDARY_LINK = `${BUTTON_BASE} min-h-touch-target w-full border border-border-strong bg-surface px-4 text-sm text-fg hover:bg-surface-muted`;

/**
 * `/invite/<token>` (A-02-T12): the link from an invitation email. The token goes to the API in
 * request bodies only (`POST /api/v1/invitations/preview` then `…/accept`). States:
 * signed out (sign in / create the account with the invited email), signed in as the invited
 * email (accept; an accountant in several practices picks one), signed in as another account
 * (sign out and continue), accepted, and the dead links — invalid, already used, withdrawn,
 * expired — each with its own heading and the server's explanation.
 */
export function InviteAccept({ token }: { token: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [state, setState] = useState<State>({ kind: "loading" });
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [practices, setPractices] = useState<{ value: string; label: string }[] | null>(null);
  const [practice, setPractice] = useState<string>("");
  const practiceId = useId();

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    const [preview, session] = await Promise.all([
      apiRequest<Invitation & Numo9Error>("/api/v1/invitations/preview", {
        method: "POST",
        body: { token },
      }),
      authRequest("/auth/session"),
    ]);
    if (preview.status === 200) {
      const account = isAuthenticated(session.body)
        ? (session.body.data?.user?.email ?? null)
        : null;
      setState({ kind: "ready", invitation: preview.body, account });
      return;
    }
    const reason = deadReason(preview.status, preview.body);
    if (reason) setState({ kind: "dead", reason, detail: preview.body.detail });
    else
      setState({
        kind: "failed",
        message: requestFailureMessage(fm, preview.status, preview.retryAfter),
      });
  }, [token, fm]);

  useEffect(() => {
    void load();
  }, [load]);

  const accept = async (invitation: Invitation) => {
    if (practices && !practice) {
      setProblem(fm(messages.chooseFirst));
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      const result = await apiRequest<Numo9Error & { practice?: { message?: string }[] }>(
        "/api/v1/invitations/accept",
        { method: "POST", body: practice ? { token, practice } : { token } },
      );
      if (result.status === 200) {
        resetMyOrganisations(); // the new membership/assignment changes the org list
        setState({ kind: "done", invitation });
        return;
      }
      const reason = deadReason(result.status, result.body);
      if (reason) {
        setState({ kind: "dead", reason, detail: result.body.detail });
        return;
      }
      if (result.body.code === "invitation.wrong_account") {
        await load(); // the session changed in another tab: show the wrong-account state
        return;
      }
      if (result.body.code === "invitation.choose_practice") {
        setPractices(await practiceOptions());
        setProblem(result.body.detail ?? null);
        return;
      }
      setProblem(
        result.body.detail ??
          (typeof result.body.practice?.[0] === "string"
            ? String(result.body.practice[0])
            : null) ??
          requestFailureMessage(fm, result.status, result.retryAfter),
      );
    } finally {
      setBusy(false);
    }
  };

  const switchAccount = async () => {
    setBusy(true);
    try {
      await authRequest("/auth/session", { method: "DELETE" }); // 401 = signed out
      resetCsrfToken();
      resetMyOrganisations();
      await load();
    } finally {
      setBusy(false);
    }
  };

  if (state.kind === "loading")
    return (
      <div aria-busy="true">
        <h1 className="text-2xl font-semibold">{fm(messages.loading)}</h1>
        <Skeleton width="75%" className="mt-4" />
        <Skeleton width="50%" className="mt-2" />
      </div>
    );

  if (state.kind === "failed")
    return (
      <>
        <h1 className="text-2xl font-semibold">{fm(messages.invalidTitle)}</h1>
        <Notice tone="danger">{state.message}</Notice>
        <Button variant="primary" className="w-full" onClick={() => void load()}>
          {fm(authMessages.retry)}
        </Button>
      </>
    );

  if (state.kind === "dead") {
    const titles: Record<Dead, typeof messages.invalidTitle> = {
      invalid: messages.invalidTitle,
      used: messages.usedTitle,
      revoked: messages.revokedTitle,
      expired: messages.expiredTitle,
    };
    return (
      <div data-invite-state={state.reason}>
        <h1 className="text-2xl font-semibold">{fm(titles[state.reason])}</h1>
        {state.detail ? <p className="mt-2 text-sm text-fg-muted">{state.detail}</p> : null}
        <div className="mt-6 grid gap-3">
          <Link href={state.reason === "used" ? "/login" : "/"} className={PRIMARY_LINK}>
            {state.reason === "used" ? fm(authMessages.signIn) : fm(messages.goHome)}
          </Link>
        </div>
      </div>
    );
  }

  const { invitation } = state;
  const target = invitation.target_name;

  if (state.kind === "done")
    return (
      <div data-invite-state="accepted">
        <h1 className="text-2xl font-semibold">{fm(messages.doneTitle, { target })}</h1>
        <Notice tone="success">
          {fm(messages.doneBody, {
            inviter: invitation.inviter_name,
            role: fm(messages.role, { role: invitation.role }),
          })}
        </Notice>
        <Link href={destination(invitation)} className={PRIMARY_LINK}>
          {fm(messages.open, { target })}
        </Link>
      </div>
    );

  const details = (
    <>
      <p className="mt-2 text-base">{body(fm, invitation)}</p>
      <p className="mt-1 text-sm text-fg-muted">
        {fm(messages.forEmail, {
          email: invitation.email,
          // One date format per locale (A-10-T08): 18 Nov 2026 / 18 nov. 2026.
          expires: formatDate(new Date(invitation.expires_at), {
            locale,
            timeZone: "America/Toronto",
          }),
        })}
      </p>
    </>
  );
  const next = `/invite/${encodeURIComponent(token)}`;

  if (state.account === null)
    return (
      <div data-invite-state="signed-out">
        <h1 className="text-2xl font-semibold">{fm(messages.title, { target })}</h1>
        {details}
        <div className="mt-6 grid gap-3">
          <Link href={`/login?next=${encodeURIComponent(next)}`} className={PRIMARY_LINK}>
            {fm(messages.signInToAccept)}
          </Link>
          <Link href="/signup" className={SECONDARY_LINK}>
            {fm(authMessages.signUp)}
          </Link>
        </div>
        <p className="mt-4 text-sm text-fg-muted">
          {fm(messages.newHere, { email: invitation.email })}
        </p>
      </div>
    );

  if (!sameEmail(state.account, invitation.email))
    return (
      <div data-invite-state="wrong-account">
        <h1 className="text-2xl font-semibold">{fm(messages.wrongTitle)}</h1>
        <Notice tone="warning">
          {fm(messages.wrongBody, { invited: invitation.email, current: state.account })}
        </Notice>
        {details}
        <div className="mt-6 grid gap-3">
          <Button
            variant="primary"
            className="w-full"
            loading={busy}
            onClick={() => void switchAccount()}
          >
            {fm(messages.switchAccount)}
          </Button>
          <Link href="/" className={SECONDARY_LINK}>
            {fm(messages.keepAccount)}
          </Link>
        </div>
      </div>
    );

  return (
    <div data-invite-state="ready">
      <h1 className="text-2xl font-semibold">{fm(messages.title, { target })}</h1>
      {details}
      <p className="mt-4 text-sm">{fm(messages.signedInAs, { email: state.account })}</p>
      <div className="mt-4">
        {problem ? <Notice tone="danger">{problem}</Notice> : null}
        {practices ? (
          <div className="mb-4 grid gap-1">
            <label htmlFor={practiceId} className="text-sm font-medium text-fg">
              {fm(messages.choosePractice)}
            </label>
            <Select
              id={practiceId}
              options={practices}
              value={practice || undefined}
              placeholder={fm(messages.choosePlaceholder)}
              onValueChange={setPractice}
            />
          </div>
        ) : null}
        <Button
          variant="primary"
          className="w-full"
          loading={busy}
          onClick={() => void accept(invitation)}
        >
          {busy ? fm(authMessages.working) : fm(messages.accept)}
        </Button>
      </div>
    </div>
  );
}

/**
 * Practices the accountant can pick when the server asks (`invitation.choose_practice`): the
 * practices that give them access to organisations today (`GET /api/v1/me/organisations`).
 */
async function practiceOptions(): Promise<{ value: string; label: string }[]> {
  try {
    const orgs = await loadMyOrganisations();
    const byId = new Map<string, string>();
    for (const org of orgs)
      for (const via of org.via_practices) byId.set(via.practice_id, via.practice_name);
    return [...byId]
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  } catch {
    return [];
  }
}
