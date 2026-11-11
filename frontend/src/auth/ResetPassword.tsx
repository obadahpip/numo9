"use client";

import { BUTTON_BASE, Form, Skeleton } from "@numo9/ui";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { UseFormReturn } from "react-hook-form";
import { z } from "zod";

import { useFormLabels } from "@/components/useFormLabels";
import { defineMessages, useFormatMessage } from "@/i18n";

import { authRequest, errorCodes, fieldErrors } from "./client";
import { authMessages, requestFailureMessage } from "./messages";
import { Notice } from "./Notice";
import { PasswordField } from "./PasswordField";
import { MIN_PASSWORD_LENGTH } from "./passwordStrength";
import { SubmitButton } from "./SubmitButton";

const messages = defineMessages({
  checking: {
    id: "auth.reset.checking",
    defaultMessage: "Checking your reset link…",
    description: "Reset page while the key is checked",
  },
  title: {
    id: "auth.reset.title",
    defaultMessage: "Choose a new password",
    description: "Reset form heading",
  },
  lead: {
    id: "auth.reset.lead",
    defaultMessage:
      "For {email}. Saving it signs you out on every device; then you sign in with the new password.",
    description: "Reset form intro; {email} is the account",
  },
  newPassword: {
    id: "auth.reset.newPassword",
    defaultMessage: "New password",
    description: "Field label",
  },
  confirm: {
    id: "auth.reset.confirm",
    defaultMessage: "Type the new password again",
    description: "Field label: confirmation",
  },
  mismatch: {
    id: "auth.reset.mismatch",
    defaultMessage: "The two passwords are different. Type the same password in both fields.",
    description: "Validation: confirmation differs",
  },
  submit: {
    id: "auth.reset.submit",
    defaultMessage: "Save new password",
    description: "Reset form submit",
  },
  deadTitle: {
    id: "auth.reset.deadTitle",
    defaultMessage: "This reset link doesn't work any more",
    description: "Reset page: expired or used key",
  },
  deadBody: {
    id: "auth.reset.deadBody",
    defaultMessage:
      "Reset links work once and for 1 hour, and stop working when the password changes. Request a new link.",
    description: "Reset page: what to do about a dead link",
  },
  requestNew: {
    id: "auth.reset.requestNew",
    defaultMessage: "Request a new link",
    description: "Link to /reset",
  },
});

interface ResetValues {
  password: string;
  confirm: string;
}

type State =
  | { kind: "checking" }
  | { kind: "ready"; email: string }
  | { kind: "dead" }
  | { kind: "failed"; message: string };

/**
 * `/reset/<key>` (A-02-T11): the link from the reset email. The key is checked first
 * (`GET /auth/password/reset` with `X-Password-Reset-Key`), so a dead link says so before the user
 * types; `POST /auth/password/reset` answers 401 when the password is set (the user is signed out
 * everywhere and signs in again) — the screen then goes to `/login?reset=done`.
 */
export function ResetPassword({ resetKey }: { resetKey: string }) {
  const fm = useFormatMessage();
  const labels = useFormLabels();
  const [state, setState] = useState<State>({ kind: "checking" });
  const [problem, setProblem] = useState<string | null>(null);
  const schema = useMemo(
    () =>
      z
        .object({
          password: z.string().min(MIN_PASSWORD_LENGTH, fm(authMessages.passwordTooShort)),
          confirm: z.string(),
        })
        .refine((values) => values.password === values.confirm, {
          path: ["confirm"],
          message: fm(messages.mismatch),
        }),
    [fm],
  );

  useEffect(() => {
    let cancelled = false;
    void authRequest("/auth/password/reset", {
      headers: { "X-Password-Reset-Key": resetKey },
    }).then((result) => {
      if (cancelled) return;
      const email = (result.body.data?.user as { email?: string } | undefined)?.email ?? "";
      if (result.status === 200) setState({ kind: "ready", email });
      else if (result.status === 400 || result.status === 404) setState({ kind: "dead" });
      else setState({ kind: "failed", message: requestFailureMessage(fm, result.status) });
    });
    return () => {
      cancelled = true;
    };
  }, [resetKey, fm]);

  const submit = async (values: ResetValues, form: UseFormReturn<ResetValues>) => {
    setProblem(null);
    const result = await authRequest("/auth/password/reset", {
      method: "POST",
      body: { key: resetKey, password: values.password },
    });
    if (result.status === 401 || result.status === 200) {
      window.location.assign("/login?reset=done");
      return;
    }
    if (result.status === 400 && errorCodes(result.body).includes("invalid_password_reset")) {
      setState({ kind: "dead" });
      return;
    }
    if (result.status === 400) {
      const password = fieldErrors(result.body).password;
      if (password?.length) {
        form.setError(
          "password",
          { type: "server", message: password.map((e) => e.message).join(" ") },
          { shouldFocus: true },
        );
        return;
      }
    }
    setProblem(requestFailureMessage(fm, result.status, result.retryAfter));
  };

  if (state.kind === "checking")
    return (
      <div aria-busy="true">
        <h1 className="text-2xl font-semibold">{fm(messages.checking)}</h1>
        <Skeleton width="75%" className="mt-4" />
      </div>
    );
  if (state.kind === "dead" || state.kind === "failed")
    return (
      <>
        <h1 className="text-2xl font-semibold">{fm(messages.deadTitle)}</h1>
        {state.kind === "failed" ? (
          <Notice tone="danger">{state.message}</Notice>
        ) : (
          <p className="mt-2 text-sm text-fg-muted">{fm(messages.deadBody)}</p>
        )}
        <Link
          href="/reset"
          className={`${BUTTON_BASE} mt-6 min-h-touch-target w-full bg-surface-accent px-4 text-sm text-fg-on-accent hover:bg-surface-accent-hover`}
        >
          {fm(messages.requestNew)}
        </Link>
      </>
    );
  return (
    <>
      <h1 className="text-2xl font-semibold">{fm(messages.title)}</h1>
      <p className="mt-2 text-sm text-fg-muted">{fm(messages.lead, { email: state.email })}</p>
      <div className="mt-6">
        {problem ? <Notice tone="danger">{problem}</Notice> : null}
        <Form<z.ZodType<ResetValues, ResetValues>>
          schema={schema as unknown as z.ZodType<ResetValues, ResetValues>}
          defaultValues={{ password: "", confirm: "" }}
          onSubmit={submit}
          labels={labels}
          saveBar={false}
          guard={false}
          aria-label={fm(messages.title)}
          className="grid gap-4"
        >
          <PasswordField
            name="password"
            label={fm(messages.newPassword)}
            autoComplete="new-password"
            meter
          />
          <PasswordField name="confirm" label={fm(messages.confirm)} autoComplete="new-password" />
          <SubmitButton label={fm(messages.submit)} busyLabel={fm(authMessages.working)} />
        </Form>
      </div>
    </>
  );
}
