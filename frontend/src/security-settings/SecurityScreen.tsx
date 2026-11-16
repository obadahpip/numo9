"use client";

import {
  Badge,
  Button,
  Dialog,
  ErrorState,
  formatDateTime,
  Input,
  LoadingRegion,
  SkeletonText,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState } from "react";

import type { ApiResult, AuthBody } from "@/auth/client";
import { defineMessages, useFormatMessage } from "@/i18n";

import {
  endSessions,
  listAuthenticators,
  listSessions,
  needsReauthentication,
  reauthenticate,
  regenerateRecoveryCodes,
  totpActivate,
  totpDeactivate,
  totpSetup,
  type Authenticator,
  type Session,
} from "./api";

const m = defineMessages({
  title: { id: "security.title", defaultMessage: "Security", description: "Page heading" },
  intro: {
    id: "security.intro",
    defaultMessage:
      "Protect your Numo9 account: two-factor authentication, recovery codes and where you're signed in.",
    description: "Text under the heading",
  },
  twoFactor: {
    id: "security.twoFactor",
    defaultMessage: "Two-factor authentication",
    description: "Section heading",
  },
  on: { id: "security.on", defaultMessage: "On", description: "2FA status" },
  off: { id: "security.off", defaultMessage: "Off", description: "2FA status" },
  offBody: {
    id: "security.offBody",
    defaultMessage:
      "Add a second step at sign-in: a 6-digit code from an authenticator app on your phone.",
    description: "2FA off explanation",
  },
  onBody: {
    id: "security.onBody",
    defaultMessage: "Signing in asks for a code from your authenticator app.",
    description: "2FA on explanation",
  },
  turnOn: {
    id: "security.turnOn",
    defaultMessage: "Turn on two-factor authentication",
    description: "Button",
  },
  turnOff: { id: "security.turnOff", defaultMessage: "Turn off", description: "Button" },
  scan: {
    id: "security.scan",
    defaultMessage:
      "Scan this QR code with your authenticator app, or enter the key by hand, then type the 6-digit code it shows.",
    description: "Enrolment instructions",
  },
  qr: {
    id: "security.qr",
    defaultMessage: "QR code for your authenticator app",
    description: "QR image alt",
  },
  key: { id: "security.key", defaultMessage: "Key: {secret}", description: "TOTP secret" },
  code: { id: "security.code", defaultMessage: "Code from the app", description: "Field" },
  activate: {
    id: "security.activate",
    defaultMessage: "Verify and turn on",
    description: "Button",
  },
  wrongCode: {
    id: "security.wrongCode",
    defaultMessage: "That code didn't work. Enter the code your app shows now.",
    description: "Error",
  },
  recovery: {
    id: "security.recovery",
    defaultMessage: "Recovery codes",
    description: "Section heading",
  },
  recoveryCount: {
    id: "security.recoveryCount",
    defaultMessage:
      "{unused} of {total} codes unused. Each code works once if you lose your phone.",
    description: "Recovery code status",
  },
  recoveryNeed: {
    id: "security.recoveryNeed",
    defaultMessage: "Recovery codes come with two-factor authentication.",
    description: "Recovery codes when 2FA is off",
  },
  regenerate: {
    id: "security.regenerate",
    defaultMessage: "Make new recovery codes",
    description: "Button",
  },
  codesTitle: {
    id: "security.codesTitle",
    defaultMessage: "Save your recovery codes now",
    description: "Heading over the codes",
  },
  codesBody: {
    id: "security.codesBody",
    defaultMessage:
      "They're shown only this once. Keep them somewhere safe, away from your phone. Any older codes stop working.",
    description: "Text with the codes",
  },
  codesList: {
    id: "security.codesList",
    defaultMessage: "Recovery codes",
    description: "List label",
  },
  saved: { id: "security.saved", defaultMessage: "I've saved them", description: "Button" },
  sessions: {
    id: "security.sessions",
    defaultMessage: "Where you're signed in",
    description: "Section heading",
  },
  device: { id: "security.device", defaultMessage: "Device", description: "Column" },
  ip: { id: "security.ip", defaultMessage: "IP address", description: "Column" },
  lastActive: { id: "security.lastActive", defaultMessage: "Last active", description: "Column" },
  thisDevice: { id: "security.thisDevice", defaultMessage: "This device", description: "Badge" },
  signOut: { id: "security.signOut", defaultMessage: "Sign out", description: "Button" },
  actions: {
    id: "security.actions",
    defaultMessage: "Actions",
    description: "Column (screen readers)",
  },
  signOutWhich: {
    id: "security.signOutWhich",
    defaultMessage: "Sign out {device} ({ip})",
    description: "Accessible name of a sign-out button",
  },
  signOutOthers: {
    id: "security.signOutOthers",
    defaultMessage: "Sign out other sessions",
    description: "Button",
  },
  signedOut: {
    id: "security.signedOut",
    defaultMessage:
      "{count, plural, one {# session was signed out.} other {# sessions were signed out.}}",
    description: "Announced after revoking",
  },
  reauthTitle: {
    id: "security.reauthTitle",
    defaultMessage: "Confirm it's you",
    description: "Dialog title",
  },
  reauthBody: {
    id: "security.reauthBody",
    defaultMessage: "Enter your password to change your security settings.",
    description: "Dialog text",
  },
  password: { id: "security.password", defaultMessage: "Password", description: "Field" },
  confirm: { id: "security.confirm", defaultMessage: "Confirm", description: "Button" },
  wrongPassword: {
    id: "security.wrongPassword",
    defaultMessage: "That password is incorrect.",
    description: "Error",
  },
  cancel: { id: "security.cancel", defaultMessage: "Cancel", description: "Button" },
  close: { id: "security.close", defaultMessage: "Close", description: "Close button" },
  failed: {
    id: "security.failed",
    defaultMessage: "That didn't work. Try again in a moment.",
    description: "Generic error",
  },
  loading: {
    id: "security.loading",
    defaultMessage: "Loading your security settings…",
    description: "Loading",
  },
  loadFailed: {
    id: "security.loadFailed",
    defaultMessage: "Your security settings couldn't be loaded",
    description: "Error title",
  },
  loadFailedBody: {
    id: "security.loadFailedBody",
    defaultMessage: "Sign in again, or verify your connection and try again.",
    description: "Error body",
  },
  retry: { id: "security.retry", defaultMessage: "Try again", description: "Retry" },
});

type Locale = "en-CA" | "fr-CA";
type Action = () => Promise<ApiResult<AuthBody>>;

/**
 * Account → Security (A-02-T13): two-factor authentication on/off (QR + key + code), recovery
 * codes (count, make new ones — shown once), and the session list with sign out one / sign out
 * the others. Changes allauth protects ask for the password first (re-authentication dialog).
 */
export function SecurityScreen() {
  const fm = useFormatMessage();
  const locale = useLocale() as Locale;
  const [sessions, setSessions] = useState<Session[] | null>(null);
  const [authenticators, setAuthenticators] = useState<Authenticator[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [status, setStatus] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [pending, setPending] = useState<{
    action: Action;
    done: (a: ApiResult<AuthBody>) => void;
  } | null>(null);

  const load = useCallback(async () => {
    setFailed(false);
    const [s, a] = await Promise.all([listSessions(), listAuthenticators()]);
    if (s.status !== 200 || a.status !== 200) {
      setFailed(true);
      return;
    }
    setSessions(s.body.data);
    setAuthenticators(a.body.data);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  /** Run a protected change; when allauth wants the password, ask, then run it again. */
  const protectedCall = async (action: Action, done: (answer: ApiResult<AuthBody>) => void) => {
    const answer = await action();
    if (needsReauthentication(answer)) setPending({ action, done });
    else done(answer);
  };

  const signOut = async (ids: number[]) => {
    const answer = await endSessions(ids);
    if (answer.status === 200 && Array.isArray(answer.body.data)) {
      setSessions(answer.body.data);
      setStatus(fm(m.signedOut, { count: ids.length }));
    } else setStatus(fm(m.failed));
  };

  const totp = authenticators?.find((a) => a.type === "totp");
  const recovery = authenticators?.find((a) => a.type === "recovery_codes");

  if (failed)
    return (
      <ErrorState
        title={fm(m.loadFailed)}
        body={fm(m.loadFailedBody)}
        retryLabel={fm(m.retry)}
        onRetry={() => void load()}
      />
    );
  if (sessions === null || authenticators === null)
    return (
      <LoadingRegion label={fm(m.loading)}>
        <SkeletonText lines={8} />
      </LoadingRegion>
    );

  const others = sessions.filter((s) => !s.is_current);
  return (
    <div className="flex max-w-4xl flex-col gap-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">{fm(m.title)}</h1>
        <p className="text-fg-muted">{fm(m.intro)}</p>
      </header>
      <p role="status" aria-live="polite" className="text-fg-muted" data-security-status>
        {status}
      </p>

      <TwoFactorSection
        enabled={Boolean(totp)}
        onChanged={(newCodes) => {
          if (newCodes) setCodes(newCodes);
          void load();
        }}
        protectedCall={protectedCall}
      />

      <section aria-labelledby="security-recovery" className="flex flex-col gap-3">
        <h2 id="security-recovery" className="text-xl font-semibold">
          {fm(m.recovery)}
        </h2>
        {recovery ? (
          <>
            <p>
              {fm(m.recoveryCount, {
                unused: recovery.unused_code_count ?? 0,
                total: recovery.total_code_count ?? 10,
              })}
            </p>
            <Button
              className="self-start"
              onClick={() =>
                void protectedCall(regenerateRecoveryCodes as Action, (answer) => {
                  const fresh = (answer.body.data as Authenticator | undefined)?.unused_codes;
                  if (answer.status === 200 && fresh) {
                    setCodes(fresh);
                    void load();
                  } else setStatus(fm(m.failed));
                })
              }
            >
              {fm(m.regenerate)}
            </Button>
          </>
        ) : (
          <p className="text-fg-muted">{fm(m.recoveryNeed)}</p>
        )}
      </section>

      <section aria-labelledby="security-sessions" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="security-sessions" className="text-xl font-semibold">
            {fm(m.sessions)}
          </h2>
          <Button
            disabled={others.length === 0}
            onClick={() => void signOut(others.map((s) => s.id))}
          >
            {fm(m.signOutOthers)}
          </Button>
        </div>
        <table className="w-full text-start">
          <thead>
            <tr className="border-b border-border text-sm text-fg-muted">
              <th scope="col" className="py-2 text-start font-medium">
                {fm(m.device)}
              </th>
              <th scope="col" className="py-2 text-start font-medium">
                {fm(m.ip)}
              </th>
              <th scope="col" className="py-2 text-start font-medium">
                {fm(m.lastActive)}
              </th>
              <th scope="col" className="py-2">
                <span className="sr-only">{fm(m.actions)}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((session) => (
              <tr key={session.id} className="border-b border-border" data-session={session.id}>
                <th scope="row" className="py-3 text-start font-normal">
                  <span className="flex flex-wrap items-center gap-2">
                    {session.device}
                    {session.is_current ? <Badge tone="info">{fm(m.thisDevice)}</Badge> : null}
                  </span>
                </th>
                <td className="py-3">{session.ip}</td>
                <td className="py-3">
                  {formatDateTime(new Date(1000 * (session.last_seen_at ?? session.created_at)), {
                    locale,
                  })}
                </td>
                <td className="py-3 text-end">
                  {session.is_current ? null : (
                    <Button
                      size="sm"
                      onClick={() => void signOut([session.id])}
                      aria-label={fm(m.signOutWhich, { device: session.device, ip: session.ip })}
                    >
                      {fm(m.signOut)}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <Dialog
        open={codes !== null}
        onOpenChange={(open) => (open ? null : setCodes(null))}
        title={fm(m.codesTitle)}
        description={fm(m.codesBody)}
        closeLabel={fm(m.close)}
        dismissible={false}
        footer={
          <Button variant="primary" onClick={() => setCodes(null)}>
            {fm(m.saved)}
          </Button>
        }
      >
        <ul
          aria-label={fm(m.codesList)}
          className="grid grid-cols-2 gap-2 font-mono"
          data-recovery-codes
        >
          {(codes ?? []).map((code) => (
            <li key={code}>{code}</li>
          ))}
        </ul>
      </Dialog>

      <ReauthDialog
        open={pending !== null}
        onCancel={() => setPending(null)}
        onConfirmed={async () => {
          if (!pending) return;
          const { action, done } = pending;
          setPending(null);
          done(await action());
        }}
      />
    </div>
  );
}

function TwoFactorSection({
  enabled,
  onChanged,
  protectedCall,
}: Readonly<{
  enabled: boolean;
  onChanged: (codes?: string[]) => void;
  protectedCall: (action: Action, done: (a: ApiResult<AuthBody>) => void) => Promise<void>;
}>) {
  const fm = useFormatMessage();
  const codeId = useId();
  const [setup, setSetup] = useState<{ qr: string; secret: string } | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");

  const start = () =>
    void protectedCall(totpSetup, (answer) => {
      const meta = answer.body.meta as { qr_code?: string; secret?: string } | undefined;
      if (meta?.secret) setSetup({ qr: meta.qr_code ?? "", secret: meta.secret });
      else setError(fm(m.failed));
    });

  const activate = () =>
    void protectedCall(
      () => totpActivate(code),
      (answer) => {
        if (answer.status === 200) {
          const recovery = (answer.body.meta as { recovery_codes?: string[] } | undefined)
            ?.recovery_codes;
          setSetup(null);
          setCode("");
          onChanged(recovery);
        } else setError(fm(m.wrongCode));
      },
    );

  return (
    <section aria-labelledby="security-2fa" className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <h2 id="security-2fa" className="text-xl font-semibold">
          {fm(m.twoFactor)}
        </h2>
        <Badge tone={enabled ? "success" : "neutral"} data-two-factor={enabled ? "on" : "off"}>
          {enabled ? fm(m.on) : fm(m.off)}
        </Badge>
      </div>
      <p className="text-fg-muted">{enabled ? fm(m.onBody) : fm(m.offBody)}</p>
      {enabled ? (
        <Button
          className="self-start"
          onClick={() => void protectedCall(totpDeactivate, () => onChanged())}
        >
          {fm(m.turnOff)}
        </Button>
      ) : setup ? (
        <form
          className="flex max-w-md flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            activate();
          }}
        >
          <p>{fm(m.scan)}</p>
          {/* The QR code is an inline data: SVG from the API — nothing for next/image to optimise. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {setup.qr ? <img src={setup.qr} alt={fm(m.qr)} width={180} height={180} /> : null}
          <p className="font-mono text-sm break-all">{fm(m.key, { secret: setup.secret })}</p>
          <label htmlFor={codeId} className="font-medium">
            {fm(m.code)}
          </label>
          <Input
            id={codeId}
            inputMode="numeric"
            autoComplete="one-time-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            aria-describedby={`${codeId}-error`}
            aria-invalid={error ? true : undefined}
          />
          <span id={`${codeId}-error`} role="alert" className="text-fg-danger">
            {error}
          </span>
          <Button type="submit" variant="primary" className="self-start">
            {fm(m.activate)}
          </Button>
        </form>
      ) : (
        <Button variant="primary" className="self-start" onClick={start}>
          {fm(m.turnOn)}
        </Button>
      )}
    </section>
  );
}

function ReauthDialog({
  open,
  onCancel,
  onConfirmed,
}: Readonly<{ open: boolean; onCancel: () => void; onConfirmed: () => Promise<void> }>) {
  const fm = useFormatMessage();
  const id = useId();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const submit = async () => {
    const answer = await reauthenticate(password);
    if (answer.status === 200) {
      setPassword("");
      setError("");
      await onConfirmed();
    } else setError(fm(m.wrongPassword));
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => (value ? null : onCancel())}
      title={fm(m.reauthTitle)}
      description={fm(m.reauthBody)}
      closeLabel={fm(m.close)}
      footer={
        <>
          <Button onClick={onCancel}>{fm(m.cancel)}</Button>
          <Button variant="primary" onClick={() => void submit()}>
            {fm(m.confirm)}
          </Button>
        </>
      }
    >
      <label htmlFor={id} className="font-medium">
        {fm(m.password)}
      </label>
      <Input
        id={id}
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        aria-describedby={`${id}-error`}
      />
      <span id={`${id}-error`} role="alert" className="text-fg-danger">
        {error}
      </span>
    </Dialog>
  );
}
