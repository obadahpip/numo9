"use client";

import { Button, Form, TextField } from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useMemo, useRef, useState, type RefObject } from "react";
import type { UseFormReturn } from "react-hook-form";
import { z } from "zod";

import { useFormLabels } from "@/components/useFormLabels";
import { defineMessages, useFormatMessage, type FormatMessage } from "@/i18n";

import { authRequest, fieldErrors, isAuthenticated, pendingFlow } from "./client";
import { authMessages, requestFailureMessage } from "./messages";
import { Notice } from "./Notice";
import { PasswordField } from "./PasswordField";
import { MIN_PASSWORD_LENGTH } from "./passwordStrength";
import { SubmitButton } from "./SubmitButton";

export type SignupPath = "accountant" | "organisation";

const messages = defineMessages({
  chooseTitle: {
    id: "auth.signup.chooseTitle",
    defaultMessage: "Create your Numo9 account",
    description: "Sign-up step 1 heading: choose accountant or business",
  },
  chooseLead: {
    id: "auth.signup.chooseLead",
    defaultMessage: "Tell us who you are so we set up the right workspace.",
    description: "Sign-up step 1 intro",
  },
  accountant: {
    id: "auth.signup.accountant",
    defaultMessage: "I'm an accountant",
    description: "Sign-up path choice: accountant / bookkeeper",
  },
  accountantDetail: {
    id: "auth.signup.accountantDetail",
    defaultMessage: "Free for accountants, always. Set up your practice and invite your clients.",
    description: "Explains the accountant sign-up path",
  },
  organisation: {
    id: "auth.signup.organisation",
    defaultMessage: "I run a business",
    description: "Sign-up path choice: business owner",
  },
  organisationDetail: {
    id: "auth.signup.organisationDetail",
    defaultMessage: "Start a 30-day free trial for your organisation. No card needed to start.",
    description: "Explains the business sign-up path",
  },
  haveAccount: {
    id: "auth.signup.haveAccount",
    defaultMessage: "Already have an account?",
    description: "Sign-up page: lead-in to the sign-in link",
  },
  formTitleAccountant: {
    id: "auth.signup.formTitleAccountant",
    defaultMessage: "Create your free accountant account",
    description: "Sign-up form heading, accountant path",
  },
  formTitleOrganisation: {
    id: "auth.signup.formTitleOrganisation",
    defaultMessage: "Start your free 30-day trial",
    description: "Sign-up form heading, business path",
  },
  name: { id: "auth.signup.name", defaultMessage: "Your name", description: "Field label" },
  practiceName: {
    id: "auth.signup.practiceName",
    defaultMessage: "Practice name",
    description: "Field label: name of the accounting practice",
  },
  practiceHint: {
    id: "auth.signup.practiceHint",
    defaultMessage: "As your clients know it, e.g. 'Maple Leaf Accounting'.",
    description: "Hint under the practice name field",
  },
  organisationName: {
    id: "auth.signup.organisationName",
    defaultMessage: "Business name",
    description: "Field label: name of the business",
  },
  organisationHint: {
    id: "auth.signup.organisationHint",
    defaultMessage: "You can add the legal name, BN and Province later.",
    description: "Hint under the business name field",
  },
  submit: {
    id: "auth.signup.submit",
    defaultMessage: "Create account",
    description: "Sign-up form submit button",
  },
  changePath: {
    id: "auth.signup.changePath",
    defaultMessage: "Choose a different account type",
    description: "Sign-up form: go back to the accountant/business choice",
  },
  nameRequired: {
    id: "auth.signup.nameRequired",
    defaultMessage: "Enter your full name, e.g. 'Dana Lee'.",
    description: "Validation: name missing",
  },
  practiceRequired: {
    id: "auth.signup.practiceRequired",
    defaultMessage: "Enter your practice's name, e.g. 'Maple Leaf Accounting'.",
    description: "Validation: practice name missing",
  },
  organisationRequired: {
    id: "auth.signup.organisationRequired",
    defaultMessage: "Enter your business name, e.g. 'Refined Interiors Inc.'.",
    description: "Validation: business name missing",
  },
  sentTitle: {
    id: "auth.signup.sentTitle",
    defaultMessage: "Open the link we emailed you",
    description: "Heading after sign-up: verification email sent",
  },
  sentBody: {
    id: "auth.signup.sentBody",
    defaultMessage:
      "We sent a link to {email}. Open it within 3 days to verify your address — then you can sign in.",
    description: "After sign-up; {email} is the address entered",
  },
  sentSpam: {
    id: "auth.signup.sentSpam",
    defaultMessage:
      "Nothing after a few minutes? Look in your spam or junk folder. If the address was mistyped, sign up again with the right one.",
    description: "After sign-up: what to do if the email doesn't arrive",
  },
  sentRetry: {
    id: "auth.signup.sentRetry",
    defaultMessage: "Use a different email address",
    description: "Button after sign-up: back to the form to fix the email",
  },
  alreadySignedIn: {
    id: "auth.signup.alreadySignedIn",
    defaultMessage:
      "You're already signed in. Go to Home, or sign out first to create another account.",
    description: "Sign-up refused because a session exists",
  },
  goHome: { id: "auth.signup.goHome", defaultMessage: "Go to Home", description: "Link to /" },
});

/** API field (allauth `param`) → form field. */
const FIELD_OF_PARAM: Record<string, keyof SignupValues> = {
  name: "name",
  email: "email",
  password: "password",
  password1: "password",
  practice_name: "practiceName",
  organisation_name: "organisationName",
};

interface SignupValues {
  name: string;
  email: string;
  password: string;
  practiceName: string;
  organisationName: string;
}

function signupSchema(path: SignupPath, fm: FormatMessage) {
  return z
    .object({
      name: z.string().trim().min(1, fm(messages.nameRequired)),
      email: z
        .string()
        .trim()
        .pipe(z.email(fm(authMessages.emailInvalid))),
      password: z.string().min(MIN_PASSWORD_LENGTH, fm(authMessages.passwordTooShort)),
      practiceName: z.string().trim(),
      organisationName: z.string().trim(),
    })
    .superRefine((values, ctx) => {
      if (path === "accountant" && !values.practiceName) {
        ctx.addIssue({
          code: "custom",
          path: ["practiceName"],
          message: fm(messages.practiceRequired),
        });
      }
      if (path === "organisation" && !values.organisationName) {
        ctx.addIssue({
          code: "custom",
          path: ["organisationName"],
          message: fm(messages.organisationRequired),
        });
      }
    });
}

/** "en-CA" | "fr-CA" | "en-XA" → the API's locale ("en-ca" | "fr-ca"). */
export function apiLocale(locale: string): "en-ca" | "fr-ca" {
  return locale.toLowerCase().startsWith("fr") ? "fr-ca" : "en-ca";
}

type Step =
  | { kind: "choose" }
  | { kind: "form"; path: SignupPath }
  | { kind: "sent"; email: string; path: SignupPath };

/**
 * Sign-up (A-02-T10, flow F1/F2): choose the path → four fields → "check your email". The
 * account is created by `POST /_allauth/browser/v1/auth/signup`; the server answers 401 with the
 * pending `verify_email` flow (verification is mandatory), and the same for an address that
 * already has an account (no enumeration), so both land on the "check your email" step.
 */
export function SignupFlow({ initialPath }: { initialPath?: SignupPath }) {
  const [step, setStep] = useState<Step>(
    initialPath ? { kind: "form", path: initialPath } : { kind: "choose" },
  );
  const heading = useRef<HTMLHeadingElement>(null);
  const first = useRef(true);
  useEffect(() => {
    // Each step change moves focus to the new heading, so keyboard and screen-reader users
    // start at the top of the new step (not on the first render).
    if (first.current) {
      first.current = false;
      return;
    }
    heading.current?.focus();
  }, [step]);

  if (step.kind === "choose")
    return <ChoosePath headingRef={heading} onChoose={(path) => setStep({ kind: "form", path })} />;
  if (step.kind === "sent")
    return (
      <SentStep
        headingRef={heading}
        email={step.email}
        onRetry={() => setStep({ kind: "form", path: step.path })}
      />
    );
  return (
    <SignupForm
      key={step.path}
      headingRef={heading}
      path={step.path}
      onBack={() => setStep({ kind: "choose" })}
      onSent={(email) => setStep({ kind: "sent", email, path: step.path })}
    />
  );
}

type HeadingRef = RefObject<HTMLHeadingElement | null>;

function ChoosePath({
  headingRef,
  onChoose,
}: {
  headingRef: HeadingRef;
  onChoose: (path: SignupPath) => void;
}) {
  const fm = useFormatMessage();
  const choices: { path: SignupPath; title: string; detail: string }[] = [
    { path: "accountant", title: fm(messages.accountant), detail: fm(messages.accountantDetail) },
    {
      path: "organisation",
      title: fm(messages.organisation),
      detail: fm(messages.organisationDetail),
    },
  ];
  return (
    <>
      <h1 ref={headingRef} tabIndex={-1} className="text-2xl font-semibold outline-none">
        {fm(messages.chooseTitle)}
      </h1>
      <p className="mt-2 text-sm text-fg-muted">{fm(messages.chooseLead)}</p>
      <ul className="mt-6 grid gap-3">
        {choices.map((choice) => (
          <li key={choice.path}>
            <button
              type="button"
              data-path={choice.path}
              onClick={() => onChoose(choice.path)}
              className="w-full min-h-touch-target rounded-lg border-2 border-border-strong bg-surface p-4 text-start hover:border-border-accent hover:bg-surface-accent-subtle"
            >
              <span className="block text-base font-semibold text-fg">{choice.title}</span>
              <span className="mt-1 block text-sm text-fg-muted">{choice.detail}</span>
            </button>
          </li>
        ))}
      </ul>
      <p className="mt-6 text-sm">
        {fm(messages.haveAccount)}
        <Link href="/login" className="ms-1 font-medium text-fg-link underline">
          {fm(authMessages.signIn)}
        </Link>
      </p>
    </>
  );
}

function SignupForm({
  headingRef,
  path,
  onBack,
  onSent,
}: {
  headingRef: HeadingRef;
  path: SignupPath;
  onBack: () => void;
  onSent: (email: string) => void;
}) {
  const fm = useFormatMessage();
  const labels = useFormLabels();
  const locale = useLocale();
  const schema = useMemo(() => signupSchema(path, fm), [path, fm]);
  const [problem, setProblem] = useState<"signedIn" | string | null>(null);

  const submit = async (values: SignupValues, form: UseFormReturn<SignupValues>) => {
    setProblem(null);
    const result = await authRequest("/auth/signup", {
      method: "POST",
      body: {
        path,
        name: values.name,
        email: values.email,
        password: values.password,
        ...(path === "accountant"
          ? { practice_name: values.practiceName }
          : { organisation_name: values.organisationName }),
        locale: apiLocale(locale),
      },
    });
    if (result.status === 401 && pendingFlow(result.body) === "verify_email") {
      onSent(values.email);
      return;
    }
    if (result.status === 200 && isAuthenticated(result.body)) {
      window.location.assign("/");
      return;
    }
    if (result.status === 409) {
      setProblem("signedIn");
      return;
    }
    if (result.status === 400) {
      const byField = fieldErrors(result.body);
      let focused = false;
      const general: string[] = [];
      for (const [param, errors] of Object.entries(byField)) {
        const field = FIELD_OF_PARAM[param];
        const message = errors.map((e) => e.message).join(" ");
        if (field) {
          form.setError(field, { type: "server", message }, { shouldFocus: !focused });
          focused = true;
        } else {
          general.push(message);
        }
      }
      if (general.length) setProblem(general.join(" "));
      return;
    }
    setProblem(requestFailureMessage(fm, result.status, result.retryAfter));
  };

  const title =
    path === "accountant" ? messages.formTitleAccountant : messages.formTitleOrganisation;
  return (
    <>
      <h1 ref={headingRef} tabIndex={-1} className="text-2xl font-semibold outline-none">
        {fm(title)}
      </h1>
      <Button variant="link" className="mt-1 text-sm" onClick={onBack}>
        {fm(messages.changePath)}
      </Button>
      <div className="mt-4">
        {problem === "signedIn" ? (
          <Notice tone="danger">
            {fm(messages.alreadySignedIn)}
            <Link href="/" className="ms-1 font-medium text-fg-link underline">
              {fm(messages.goHome)}
            </Link>
          </Notice>
        ) : problem ? (
          <Notice tone="danger">{problem}</Notice>
        ) : null}
        <Form<z.ZodType<SignupValues, SignupValues>>
          schema={schema as unknown as z.ZodType<SignupValues, SignupValues>}
          defaultValues={{
            name: "",
            email: "",
            password: "",
            practiceName: "",
            organisationName: "",
          }}
          onSubmit={submit}
          labels={labels}
          saveBar={false}
          guard={false}
          aria-label={fm(title)}
          className="grid gap-4"
        >
          <TextField name="name" label={fm(messages.name)} required autoComplete="name" />
          <TextField
            name="email"
            label={fm(authMessages.email)}
            required
            type="email"
            autoComplete="email"
            inputMode="email"
            spellCheck={false}
          />
          <PasswordField
            name="password"
            label={fm(authMessages.password)}
            autoComplete="new-password"
            meter
          />
          {path === "accountant" ? (
            <TextField
              name="practiceName"
              label={fm(messages.practiceName)}
              hint={fm(messages.practiceHint)}
              required
              autoComplete="organization"
            />
          ) : (
            <TextField
              name="organisationName"
              label={fm(messages.organisationName)}
              hint={fm(messages.organisationHint)}
              required
              autoComplete="organization"
            />
          )}
          <SubmitButton label={fm(messages.submit)} busyLabel={fm(authMessages.working)} />
        </Form>
      </div>
      <p className="mt-6 text-sm">
        {fm(messages.haveAccount)}
        <Link href="/login" className="ms-1 font-medium text-fg-link underline">
          {fm(authMessages.signIn)}
        </Link>
      </p>
    </>
  );
}

function SentStep({
  headingRef,
  email,
  onRetry,
}: {
  headingRef: HeadingRef;
  email: string;
  onRetry: () => void;
}) {
  const fm = useFormatMessage();
  return (
    <>
      <h1 ref={headingRef} tabIndex={-1} className="text-2xl font-semibold outline-none">
        {fm(messages.sentTitle)}
      </h1>
      <Notice tone="success">
        <p>{fm(messages.sentBody, { email })}</p>
      </Notice>
      <p className="text-sm text-fg-muted">{fm(messages.sentSpam)}</p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Button onClick={onRetry}>{fm(messages.sentRetry)}</Button>
        <Link
          href="/login"
          className="inline-flex min-h-touch-target items-center px-2 text-sm font-medium text-fg-link underline"
        >
          {fm(authMessages.signIn)}
        </Link>
      </div>
    </>
  );
}
