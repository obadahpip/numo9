"use client";

import { Button, Checkbox, CodeInput, Input, type CodeInputHandle } from "@numo9/ui";
import Link from "next/link";
import { useId, useRef, useState, type FormEvent } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import { authRequest, errorCodes, isAuthenticated, pendingFlow } from "./client";
import { authMessages, requestFailureMessage } from "./messages";
import { Notice } from "./Notice";

const messages = defineMessages({
  title: {
    id: "auth.twoFactor.title",
    defaultMessage: "Enter your authentication code",
    description: "2FA challenge heading",
  },
  lead: {
    id: "auth.twoFactor.lead",
    defaultMessage: "Open your authenticator app and enter the 6-digit code it shows for Numo9.",
    description: "2FA challenge intro (TOTP)",
  },
  codeLabel: {
    id: "auth.twoFactor.codeLabel",
    defaultMessage: "Authentication code",
    description: "Accessible name of the 6-box code input",
  },
  digit: {
    id: "auth.twoFactor.digit",
    defaultMessage: "Digit {position, number} of {length, number}",
    description: "Accessible name of one box of the code input",
  },
  recoveryLead: {
    id: "auth.twoFactor.recoveryLead",
    defaultMessage:
      "Enter one of the 10 recovery codes you saved when you set up two-factor authentication. Each code works once.",
    description: "2FA challenge intro (recovery code)",
  },
  recoveryLabel: {
    id: "auth.twoFactor.recoveryLabel",
    defaultMessage: "Recovery code",
    description: "Field label",
  },
  recoveryHint: {
    id: "auth.twoFactor.recoveryHint",
    defaultMessage: "Looks like k7m2p-x9qrt. Capitals and dashes don't matter.",
    description: "Hint under the recovery code field",
  },
  remember: {
    id: "auth.twoFactor.remember",
    defaultMessage: "Remember this device for 30 days",
    description: "Checkbox: skip the code on this browser for 30 days",
  },
  rememberHint: {
    id: "auth.twoFactor.rememberHint",
    defaultMessage: "Only on a computer or phone that you alone use.",
    description: "Hint under the remember-device checkbox",
  },
  verify: {
    id: "auth.twoFactor.verify",
    defaultMessage: "Verify and sign in",
    description: "2FA submit button",
  },
  useRecovery: {
    id: "auth.twoFactor.useRecovery",
    defaultMessage: "Use a recovery code instead",
    description: "Switch from the app code to a recovery code",
  },
  useApp: {
    id: "auth.twoFactor.useApp",
    defaultMessage: "Use the code from your authenticator app",
    description: "Switch from a recovery code back to the app code",
  },
  codeIncomplete: {
    id: "auth.twoFactor.codeIncomplete",
    defaultMessage: "Enter all 6 digits of the code.",
    description: "Validation: code shorter than 6 digits",
  },
  recoveryMissing: {
    id: "auth.twoFactor.recoveryMissing",
    defaultMessage: "Enter a recovery code.",
    description: "Validation: recovery code empty",
  },
  wrongCode: {
    id: "auth.twoFactor.wrongCode",
    defaultMessage:
      "That code didn't work. Codes change every 30 seconds — enter the one your app shows now, and make sure your phone's clock is set automatically.",
    description: "2FA: wrong or expired TOTP code",
  },
  wrongRecovery: {
    id: "auth.twoFactor.wrongRecovery",
    defaultMessage:
      "That recovery code didn't work. It may have been used already — each code works once. Try another one.",
    description: "2FA: wrong or used recovery code",
  },
  expired: {
    id: "auth.twoFactor.expired",
    defaultMessage: "Your sign-in timed out before the code was entered. Sign in again.",
    description: "2FA: the pending login is gone (session expired)",
  },
  lostDevice: {
    id: "auth.twoFactor.lostDevice",
    defaultMessage:
      "Lost your phone and your recovery codes? Ask your practice admin or Numo9 support to reset two-factor authentication — they will confirm who you are first.",
    description: "2FA: what to do without app or recovery codes",
  },
});

type Mode = "totp" | "recovery";

/**
 * 2FA challenge (A-02-T11): after the password, the server answers `401` with the pending
 * `mfa_authenticate` flow. The 6-digit TOTP (CodeInput: auto-advance, paste-aware, submits when
 * complete) or a recovery code goes to `POST /auth/2fa/authenticate`; then `mfa_trust` is answered
 * with the "remember this device" choice (`POST /auth/2fa/trust`).
 */
export function TwoFactorStep({ onSignedIn }: { onSignedIn: () => void }) {
  const fm = useFormatMessage();
  const [mode, setMode] = useState<Mode>("totp");
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState<{ text: string; expired?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const codeInput = useRef<CodeInputHandle>(null);
  const recoveryInput = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const errorId = useId();
  const recoveryId = useId();

  const focusEntry = (which: Mode = mode) => {
    if (which === "totp") codeInput.current?.focus();
    else recoveryInput.current?.focus();
  };

  const submit = async (value: string) => {
    if (busy) return;
    if (mode === "totp" && value.length !== 6) {
      setError({ text: fm(messages.codeIncomplete) });
      focusEntry();
      return;
    }
    if (mode === "recovery" && !value.trim()) {
      setError({ text: fm(messages.recoveryMissing) });
      focusEntry();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await authRequest("/auth/2fa/authenticate", {
        method: "POST",
        body: { code: value.trim() },
      });
      if (result.status === 200 && isAuthenticated(result.body)) {
        onSignedIn();
        return;
      }
      if (result.status === 401 && pendingFlow(result.body) === "mfa_trust") {
        const trusted = await authRequest("/auth/2fa/trust", {
          method: "POST",
          body: { trust: remember },
        });
        if (trusted.status === 200 && isAuthenticated(trusted.body)) {
          onSignedIn();
          return;
        }
        setError({ text: requestFailureMessage(fm, trusted.status, trusted.retryAfter) });
        return;
      }
      if (result.status === 400 && errorCodes(result.body).includes("incorrect_code")) {
        setError({ text: fm(mode === "totp" ? messages.wrongCode : messages.wrongRecovery) });
        if (mode === "totp") {
          setCode("");
          codeInput.current?.focus(0); // start again at the first box
        } else {
          recoveryInput.current?.select();
        }
        return;
      }
      if (result.status === 401 || result.status === 409) {
        setError({ text: fm(messages.expired), expired: true });
        return;
      }
      setError({ text: requestFailureMessage(fm, result.status, result.retryAfter) });
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    void submit(mode === "totp" ? code : recovery);
  };

  const switchMode = () => {
    const next: Mode = mode === "totp" ? "recovery" : "totp";
    setMode(next);
    setError(null);
    setTimeout(() => focusEntry(next), 0);
  };

  return (
    <>
      <h1 ref={heading} tabIndex={-1} className="text-2xl font-semibold outline-none">
        {fm(messages.title)}
      </h1>
      <p className="mt-2 text-sm text-fg-muted">
        {fm(mode === "totp" ? messages.lead : messages.recoveryLead)}
      </p>
      <form
        noValidate
        onSubmit={onSubmit}
        className="mt-6 grid gap-4"
        aria-label={fm(messages.title)}
      >
        {error ? (
          <Notice tone="danger" id={errorId}>
            {error.text}
            {error.expired ? (
              <Link href="/login" className="ms-1 font-medium text-fg-link underline">
                {fm(authMessages.signIn)}
              </Link>
            ) : null}
          </Notice>
        ) : null}
        {mode === "totp" ? (
          <CodeInput
            ref={codeInput}
            value={code}
            onChange={setCode}
            onComplete={(full) => void submit(full)}
            label={fm(messages.codeLabel)}
            digitLabel={(position, length) => fm(messages.digit, { position, length })}
            invalid={Boolean(error) && !error?.expired}
            aria-describedby={error ? errorId : undefined}
            autoFocus
          />
        ) : (
          <div className="grid gap-1">
            <label htmlFor={recoveryId} className="text-sm font-medium text-fg">
              {fm(messages.recoveryLabel)}
            </label>
            <p id={`${recoveryId}-hint`} className="text-xs text-fg-muted">
              {fm(messages.recoveryHint)}
            </p>
            <Input
              ref={recoveryInput}
              id={recoveryId}
              value={recovery}
              onChange={(event) => setRecovery(event.target.value)}
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              invalid={Boolean(error) && !error?.expired}
              aria-describedby={[`${recoveryId}-hint`, error ? errorId : undefined]
                .filter(Boolean)
                .join(" ")}
            />
          </div>
        )}
        <Checkbox
          label={fm(messages.remember)}
          description={fm(messages.rememberHint)}
          checked={remember}
          onCheckedChange={(checked) => setRemember(checked === true)}
        />
        <Button type="submit" variant="primary" loading={busy} className="w-full">
          {busy ? fm(authMessages.working) : fm(messages.verify)}
        </Button>
      </form>
      <Button variant="link" className="mt-4 text-sm" onClick={switchMode}>
        {fm(mode === "totp" ? messages.useRecovery : messages.useApp)}
      </Button>
      <p className="mt-4 text-xs text-fg-muted">{fm(messages.lostDevice)}</p>
    </>
  );
}
