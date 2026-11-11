"use client";

import { BUTTON_BASE, Skeleton } from "@numo9/ui";
import Link from "next/link";
import { useEffect, useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import { authRequest, isAuthenticated, pendingFlow, resetCsrfToken } from "./client";
import { authMessages } from "./messages";
import { safeNextUrl } from "./nextUrl";
import { TwoFactorStep } from "./TwoFactorStep";

const messages = defineMessages({
  checking: {
    id: "auth.twoFactor.checking",
    defaultMessage: "Checking your sign-in…",
    description: "/2fa while the pending login is looked up",
  },
  noPending: {
    id: "auth.twoFactor.noPending",
    defaultMessage: "Sign in first",
    description: "/2fa opened without a sign-in waiting for a code: heading",
  },
  noPendingBody: {
    id: "auth.twoFactor.noPendingBody",
    defaultMessage:
      "There's no sign-in waiting for a code in this browser — it may have timed out. Sign in with your email and password, then enter the code.",
    description: "/2fa without a pending login: explanation",
  },
});

/**
 * `/2fa` (A-02-T11): the code step on its own URL (reload-safe). The pending login lives in the
 * server session; `GET /auth/session` says whether it waits for `mfa_authenticate`.
 */
export function TwoFactorPage({ next }: { next?: string }) {
  const fm = useFormatMessage();
  const [state, setState] = useState<"checking" | "pending" | "none">("checking");
  const destination = safeNextUrl(next);

  useEffect(() => {
    let cancelled = false;
    void authRequest("/auth/session").then((result) => {
      if (cancelled) return;
      if (result.status === 200 && isAuthenticated(result.body))
        window.location.assign(destination);
      else if (pendingFlow(result.body) === "mfa_authenticate") setState("pending");
      else setState("none");
    });
    return () => {
      cancelled = true;
    };
  }, [destination]);

  if (state === "pending")
    return (
      <TwoFactorStep
        onSignedIn={() => {
          resetCsrfToken();
          window.location.assign(destination);
        }}
      />
    );
  if (state === "checking")
    return (
      <div aria-busy="true">
        <h1 className="text-2xl font-semibold">{fm(messages.checking)}</h1>
        <Skeleton width="75%" className="mt-4" />
      </div>
    );
  return (
    <>
      <h1 className="text-2xl font-semibold">{fm(messages.noPending)}</h1>
      <p className="mt-2 text-sm text-fg-muted">{fm(messages.noPendingBody)}</p>
      <Link
        href={next ? `/login?next=${encodeURIComponent(destination)}` : "/login"}
        className={`${BUTTON_BASE} mt-6 min-h-touch-target w-full bg-surface-accent px-4 text-sm text-fg-on-accent hover:bg-surface-accent-hover`}
      >
        {fm(authMessages.signIn)}
      </Link>
    </>
  );
}
