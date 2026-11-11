"use client";

import { BUTTON_BASE, Button, Skeleton } from "@numo9/ui";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import { authRequest, isAuthenticated, type ApiResult, type AuthBody } from "./client";
import { authMessages, requestFailureMessage } from "./messages";
import { Notice } from "./Notice";

const messages = defineMessages({
  checkingTitle: {
    id: "auth.verify.checkingTitle",
    defaultMessage: "Verifying your email…",
    description: "Verify page while the link is checked",
  },
  verifiedTitle: {
    id: "auth.verify.verifiedTitle",
    defaultMessage: "Your email is verified",
    description: "Verify page: success heading",
  },
  verifiedSignedIn: {
    id: "auth.verify.verifiedSignedIn",
    defaultMessage: "You're signed in. Your workspace is ready.",
    description: "Verify page: verified and signed in",
  },
  verifiedSignIn: {
    id: "auth.verify.verifiedSignIn",
    defaultMessage: "Sign in with your email and password to continue.",
    description: "Verify page: verified in another browser, so the user must sign in",
  },
  continue: {
    id: "auth.verify.continue",
    defaultMessage: "Continue to Numo9",
    description: "Verify page: go to the app",
  },
  invalidTitle: {
    id: "auth.verify.invalidTitle",
    defaultMessage: "This link doesn't work any more",
    description: "Verify page: invalid, expired or used link",
  },
  invalidBody: {
    id: "auth.verify.invalidBody",
    defaultMessage:
      "Verification links work once and for 3 days. If you already verified, just sign in. Otherwise sign in anyway — we'll email you a new link.",
    description: "Verify page: what to do about a dead link",
  },
  failedTitle: {
    id: "auth.verify.failedTitle",
    defaultMessage: "We couldn't check your link",
    description: "Verify page: network/server failure heading",
  },
  retry: { id: "auth.verify.retry", defaultMessage: "Try again", description: "Retry button" },
});

/**
 * A verification key is posted once per page load — React may mount the effect twice (Strict
 * Mode) and a second post would see the key already used and wrongly report "doesn't work".
 */
const inFlight = new Map<string, Promise<ApiResult<AuthBody>>>();

function verify(key: string, retry = false): Promise<ApiResult<AuthBody>> {
  if (retry) inFlight.delete(key);
  let request = inFlight.get(key);
  if (!request) {
    request = authRequest("/auth/email/verify", { method: "POST", body: { key } });
    inFlight.set(key, request);
  }
  return request;
}

type State =
  | { kind: "checking" }
  | { kind: "verified"; signedIn: boolean }
  | { kind: "invalid" }
  | { kind: "failed"; message: string };

/**
 * `/verify/<key>` (A-02-T10): the link from the verification email. `POST /auth/email/verify`
 * verifies the address and, in the browser that signed up, signs the user in (200); in another
 * browser it verifies without a session (401) and the user signs in. 400/409: invalid, expired
 * or already used.
 */
export function VerifyEmail({ verificationKey }: { verificationKey: string }) {
  const fm = useFormatMessage();
  const [state, setState] = useState<State>({ kind: "checking" });

  const run = useCallback(
    (retry: boolean) => {
      let cancelled = false;
      setState({ kind: "checking" });
      void verify(verificationKey, retry).then((result) => {
        if (cancelled) return;
        if (result.status === 200)
          setState({ kind: "verified", signedIn: isAuthenticated(result.body) });
        else if (result.status === 401) setState({ kind: "verified", signedIn: false });
        else if (result.status === 400 || result.status === 404 || result.status === 409)
          setState({ kind: "invalid" });
        else
          setState({
            kind: "failed",
            message: requestFailureMessage(fm, result.status, result.retryAfter),
          });
      });
      return () => {
        cancelled = true;
      };
    },
    [verificationKey, fm],
  );

  useEffect(() => run(false), [run]);

  if (state.kind === "checking")
    return (
      <div aria-busy="true">
        <h1 className="text-2xl font-semibold">{fm(messages.checkingTitle)}</h1>
        <Skeleton width="75%" className="mt-4" />
      </div>
    );
  if (state.kind === "verified")
    return (
      <>
        <h1 className="text-2xl font-semibold">{fm(messages.verifiedTitle)}</h1>
        <Notice tone="success">
          {state.signedIn ? fm(messages.verifiedSignedIn) : fm(messages.verifiedSignIn)}
        </Notice>
        <Link
          href={state.signedIn ? "/" : "/login"}
          className={`${BUTTON_BASE} min-h-touch-target w-full bg-surface-accent px-4 text-sm text-fg-on-accent hover:bg-surface-accent-hover`}
        >
          {state.signedIn ? fm(messages.continue) : fm(authMessages.signIn)}
        </Link>
      </>
    );
  if (state.kind === "invalid")
    return (
      <>
        <h1 className="text-2xl font-semibold">{fm(messages.invalidTitle)}</h1>
        <p className="mt-2 text-sm text-fg-muted">{fm(messages.invalidBody)}</p>
        <Link
          href="/login"
          className={`${BUTTON_BASE} mt-6 min-h-touch-target w-full bg-surface-accent px-4 text-sm text-fg-on-accent hover:bg-surface-accent-hover`}
        >
          {fm(authMessages.signIn)}
        </Link>
      </>
    );
  return (
    <>
      <h1 className="text-2xl font-semibold">{fm(messages.failedTitle)}</h1>
      <Notice tone="danger">{state.message}</Notice>
      <Button variant="primary" className="w-full" onClick={() => run(true)}>
        {fm(messages.retry)}
      </Button>
    </>
  );
}
