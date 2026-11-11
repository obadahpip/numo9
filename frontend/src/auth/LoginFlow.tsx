"use client";

import { Form, TextField } from "@numo9/ui";
import Link from "next/link";
import { useMemo, useState } from "react";
import { z } from "zod";

import { useFormLabels } from "@/components/useFormLabels";
import { defineMessages, useFormatMessage, type FormatMessage } from "@/i18n";

import { authRequest, isAuthenticated, pendingFlow, resetCsrfToken } from "./client";
import { authMessages, requestFailureMessage } from "./messages";
import { safeNextUrl } from "./nextUrl";
import { Notice } from "./Notice";
import { PasswordField } from "./PasswordField";
import { SubmitButton } from "./SubmitButton";
import { TwoFactorStep } from "./TwoFactorStep";

const messages = defineMessages({
  title: {
    id: "auth.login.title",
    defaultMessage: "Sign in to Numo9",
    description: "Login heading",
  },
  submit: {
    id: "auth.login.submit",
    defaultMessage: "Sign in",
    description: "Login submit button",
  },
  forgot: {
    id: "auth.login.forgot",
    defaultMessage: "Forgot your password?",
    description: "Link to the password reset request",
  },
  noAccount: {
    id: "auth.login.noAccount",
    defaultMessage: "New to Numo9?",
    description: "Lead-in to the sign-up link",
  },
  mismatch: {
    id: "auth.login.mismatch",
    defaultMessage:
      "The email or password is incorrect. Try again, or reset your password if you've forgotten it.",
    description: "Login refused: wrong email or password (same for an unknown email)",
  },
  locked: {
    id: "auth.login.locked",
    defaultMessage:
      "Too many failed sign-ins. For your security, this account is locked for {minutes, plural, one {# minute} other {# minutes}}. You can reset your password now to unlock it.",
    description: "Login refused: account locked after 10 failures (Retry-After rounded up)",
  },
  verifyFirst: {
    id: "auth.login.verifyFirst",
    defaultMessage:
      "Verify your email address first. We've emailed a new link to {email} — open it, then sign in.",
    description: "Login of an account whose email is not verified yet",
  },
  alreadySignedIn: {
    id: "auth.login.alreadySignedIn",
    defaultMessage: "You're already signed in.",
    description: "Login while a session exists",
  },
  continue: {
    id: "auth.login.continue",
    defaultMessage: "Continue",
    description: "Link: continue to the app when already signed in",
  },
  resetDone: {
    id: "auth.login.resetDone",
    defaultMessage:
      "Your password was changed and every session was signed out. Sign in with your new password.",
    description: "Login page after a completed password reset (?reset=done)",
  },
});

type Step = "password" | "twoFactor";

interface LoginValues {
  email: string;
  password: string;
}

function loginSchema(fm: FormatMessage) {
  return z.object({
    email: z
      .string()
      .trim()
      .pipe(z.email(fm(authMessages.emailInvalid))),
    password: z.string().min(1, fm(authMessages.passwordRequired)),
  });
}

/**
 * Login (A-02-T11): email + password → `POST /auth/login`; then, when the account has 2FA, the
 * code step (pending `mfa_authenticate`). Wrong email and wrong password get one message (no
 * account enumeration); a locked account (429, Retry-After) says for how long and offers the
 * reset, which unlocks it (S-03-T07). After signing in the browser goes to `next` (same-site
 * paths only) or Home.
 */
export function LoginFlow({ next, notice }: { next?: string; notice?: "resetDone" }) {
  const fm = useFormatMessage();
  const labels = useFormLabels();
  const schema = useMemo(() => loginSchema(fm), [fm]);
  const [step, setStep] = useState<Step>("password");
  const [problem, setProblem] = useState<
    { kind: "text"; text: string } | { kind: "signedIn" } | { kind: "verify"; email: string } | null
  >(null);
  const destination = safeNextUrl(next);

  const signedIn = () => {
    resetCsrfToken(); // login rotates the CSRF token
    window.location.assign(destination);
  };

  const submit = async (values: LoginValues) => {
    setProblem(null);
    const result = await authRequest("/auth/login", {
      method: "POST",
      body: { email: values.email, password: values.password },
    });
    if (result.status === 200 && isAuthenticated(result.body)) {
      signedIn();
      return;
    }
    const pending = pendingFlow(result.body);
    if (result.status === 401 && pending === "mfa_authenticate") {
      setStep("twoFactor");
      return;
    }
    if (result.status === 401 && pending === "verify_email") {
      setProblem({ kind: "verify", email: values.email });
      return;
    }
    if (result.status === 401) {
      setProblem({ kind: "text", text: fm(messages.mismatch) });
      return;
    }
    if (result.status === 409) {
      setProblem({ kind: "signedIn" });
      return;
    }
    if (result.status === 429) {
      const minutes = Math.max(1, Math.ceil((result.retryAfter ?? 900) / 60));
      setProblem({ kind: "text", text: fm(messages.locked, { minutes }) });
      return;
    }
    if (result.status === 400) {
      const text = (result.body.errors ?? []).map((e) => e.message).join(" ");
      setProblem({ kind: "text", text: text || fm(messages.mismatch) });
      return;
    }
    setProblem({ kind: "text", text: requestFailureMessage(fm, result.status, result.retryAfter) });
  };

  if (step === "twoFactor") return <TwoFactorStep onSignedIn={signedIn} />;

  return (
    <>
      <h1 className="text-2xl font-semibold">{fm(messages.title)}</h1>
      <div className="mt-6">
        {notice === "resetDone" && !problem ? (
          <Notice tone="success">{fm(messages.resetDone)}</Notice>
        ) : null}
        {problem?.kind === "text" ? <Notice tone="danger">{problem.text}</Notice> : null}
        {problem?.kind === "verify" ? (
          <Notice tone="warning">{fm(messages.verifyFirst, { email: problem.email })}</Notice>
        ) : null}
        {problem?.kind === "signedIn" ? (
          <Notice tone="info">
            {fm(messages.alreadySignedIn)}
            <Link href={destination} className="ms-1 font-medium text-fg-link underline">
              {fm(messages.continue)}
            </Link>
          </Notice>
        ) : null}
        <Form<z.ZodType<LoginValues, LoginValues>>
          schema={schema as unknown as z.ZodType<LoginValues, LoginValues>}
          defaultValues={{ email: "", password: "" }}
          onSubmit={submit}
          labels={labels}
          saveBar={false}
          guard={false}
          aria-label={fm(messages.title)}
          className="grid gap-4"
        >
          <TextField
            name="email"
            label={fm(authMessages.email)}
            required
            type="email"
            autoComplete="username"
            inputMode="email"
            spellCheck={false}
          />
          <PasswordField
            name="password"
            label={fm(authMessages.password)}
            autoComplete="current-password"
          />
          <SubmitButton label={fm(messages.submit)} busyLabel={fm(authMessages.working)} />
        </Form>
      </div>
      <p className="mt-4 text-sm">
        <Link href="/reset" className="font-medium text-fg-link underline">
          {fm(messages.forgot)}
        </Link>
      </p>
      <p className="mt-2 text-sm">
        {fm(messages.noAccount)}
        <Link href="/signup" className="ms-1 font-medium text-fg-link underline">
          {fm(authMessages.signUp)}
        </Link>
      </p>
    </>
  );
}
