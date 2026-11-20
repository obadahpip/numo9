"use client";

/**
 * Social sign-in buttons (A-02-T16): "Continue with Google / Microsoft" for an existing account.
 * Shown only when allauth's configuration lists the provider — the `auth.social_signin` flag is
 * on and the provider is configured on the server; with the flag off the list is empty and no
 * button (nor the "or" divider) renders. A click posts a plain form to allauth's provider
 * redirect (the browser leaves for the provider and comes back signed in, or to
 * `/login?social=error`).
 */
import { Button } from "@numo9/ui";
import { useEffect, useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import { AUTH_API, authRequest, formCsrfToken } from "./client";

const messages = defineMessages({
  google: {
    id: "auth.social.google",
    defaultMessage: "Continue with Google",
    description: "Social sign-in button",
  },
  microsoft: {
    id: "auth.social.microsoft",
    defaultMessage: "Continue with Microsoft",
    description: "Social sign-in button",
  },
  or: {
    id: "auth.social.or",
    defaultMessage: "or use your email",
    description: "Divider between the social buttons and the email form",
  },
  error: {
    id: "auth.social.error",
    defaultMessage:
      "Signing in with that account didn't work. Sign in with your email and password, or sign up first if you're new to Numo9.",
    description: "Shown on the login page after a failed social sign-in",
  },
});

export const SOCIAL_PROVIDERS = ["google", "microsoft"] as const;
export type SocialProvider = (typeof SOCIAL_PROVIDERS)[number];

/** The providers the server offers now (empty while the flag is off). */
export function offeredProviders(body: unknown): SocialProvider[] {
  const providers =
    (body as { data?: { socialaccount?: { providers?: { id?: string }[] } } })?.data?.socialaccount
      ?.providers ?? [];
  const ids = new Set(providers.map((p) => p.id));
  return SOCIAL_PROVIDERS.filter((id) => ids.has(id));
}

async function startSocialSignIn(provider: SocialProvider, next: string): Promise<void> {
  const token = await formCsrfToken();
  const form = document.createElement("form");
  form.method = "POST";
  form.action = `${AUTH_API}/auth/provider/redirect`;
  const fields: Record<string, string> = {
    provider,
    process: "login",
    callback_url: next,
    csrfmiddlewaretoken: token,
  };
  for (const [name, value] of Object.entries(fields)) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  form.submit();
}

export function SocialSignIn({ next }: { next: string }) {
  const fm = useFormatMessage();
  const [providers, setProviders] = useState<SocialProvider[]>([]);
  const [busy, setBusy] = useState<SocialProvider | null>(null);

  useEffect(() => {
    let cancelled = false;
    void authRequest("/config").then((result) => {
      if (!cancelled && result.status === 200) setProviders(offeredProviders(result.body));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (providers.length === 0) return null;
  return (
    <div className="mt-6 flex flex-col gap-3" data-social-signin="">
      {providers.map((provider) => (
        <Button
          key={provider}
          variant="secondary"
          loading={busy === provider}
          onClick={() => {
            setBusy(provider);
            void startSocialSignIn(provider, next).catch(() => setBusy(null));
          }}
        >
          {fm(messages[provider])}
        </Button>
      ))}
      <p className="text-center text-sm text-fg-muted">{fm(messages.or)}</p>
    </div>
  );
}

export function useSocialErrorMessage(): string {
  const fm = useFormatMessage();
  return fm(messages.error);
}
