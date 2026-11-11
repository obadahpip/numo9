"use client";

import { Button, Form, TextField } from "@numo9/ui";
import Link from "next/link";
import { useMemo, useState } from "react";
import { z } from "zod";

import { useFormLabels } from "@/components/useFormLabels";
import { defineMessages, useFormatMessage } from "@/i18n";

import { authRequest } from "./client";
import { authMessages, requestFailureMessage } from "./messages";
import { Notice } from "./Notice";
import { SubmitButton } from "./SubmitButton";

const messages = defineMessages({
  title: {
    id: "auth.reset.requestTitle",
    defaultMessage: "Reset your password",
    description: "Password reset request heading",
  },
  lead: {
    id: "auth.reset.requestLead",
    defaultMessage:
      "Enter the email you sign in with. We'll email you a link to choose a new password.",
    description: "Password reset request intro",
  },
  submit: {
    id: "auth.reset.requestSubmit",
    defaultMessage: "Email me a reset link",
    description: "Password reset request button",
  },
  sentTitle: {
    id: "auth.reset.sentTitle",
    defaultMessage: "Look for our email",
    description: "Heading after a reset link was requested",
  },
  sentBody: {
    id: "auth.reset.sentBody",
    defaultMessage:
      "If {email} has a Numo9 account, a reset link is on its way. It works once, for 1 hour. Nothing arrived after a few minutes? Look in your spam folder, or request a new link.",
    description: "After the reset request; the same text whether or not the account exists",
  },
  again: {
    id: "auth.reset.again",
    defaultMessage: "Request another link",
    description: "Button: back to the reset request form",
  },
  backToLogin: {
    id: "auth.reset.backToLogin",
    defaultMessage: "Back to sign in",
    description: "Link to /login",
  },
});

/**
 * `/reset` (A-02-T11): request a reset link. `POST /auth/password/request` answers 200 for any
 * address (no enumeration), so the confirmation never says whether the account exists.
 */
export function ResetRequest() {
  const fm = useFormatMessage();
  const labels = useFormLabels();
  const schema = useMemo(
    () =>
      z.object({
        email: z
          .string()
          .trim()
          .pipe(z.email(fm(authMessages.emailInvalid))),
      }),
    [fm],
  );
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  if (sentTo)
    return (
      <>
        <h1 className="text-2xl font-semibold">{fm(messages.sentTitle)}</h1>
        <Notice tone="success">{fm(messages.sentBody, { email: sentTo })}</Notice>
        <div className="mt-6 flex flex-wrap items-center gap-3">
          <Button onClick={() => setSentTo(null)}>{fm(messages.again)}</Button>
          <Link href="/login" className="px-2 text-sm font-medium text-fg-link underline">
            {fm(messages.backToLogin)}
          </Link>
        </div>
      </>
    );

  return (
    <>
      <h1 className="text-2xl font-semibold">{fm(messages.title)}</h1>
      <p className="mt-2 text-sm text-fg-muted">{fm(messages.lead)}</p>
      <div className="mt-6">
        {problem ? <Notice tone="danger">{problem}</Notice> : null}
        <Form<z.ZodType<{ email: string }, { email: string }>>
          schema={schema as unknown as z.ZodType<{ email: string }, { email: string }>}
          defaultValues={{ email: "" }}
          onSubmit={async (values) => {
            setProblem(null);
            const result = await authRequest("/auth/password/request", {
              method: "POST",
              body: { email: values.email },
            });
            if (result.status === 200) setSentTo(values.email);
            else if (result.status === 400)
              setProblem(
                (result.body.errors ?? []).map((e) => e.message).join(" ") ||
                  fm(authMessages.emailInvalid),
              );
            else setProblem(requestFailureMessage(fm, result.status, result.retryAfter));
          }}
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
            autoComplete="email"
            inputMode="email"
            spellCheck={false}
          />
          <SubmitButton label={fm(messages.submit)} busyLabel={fm(authMessages.working)} />
        </Form>
      </div>
      <p className="mt-4 text-sm">
        <Link href="/login" className="font-medium text-fg-link underline">
          {fm(messages.backToLogin)}
        </Link>
      </p>
    </>
  );
}
