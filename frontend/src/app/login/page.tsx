import type { Metadata } from "next";

import { AuthLayout } from "@/auth/AuthLayout";
import { LoginFlow } from "@/auth/LoginFlow";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";

const messages = defineMessages({
  title: {
    id: "auth.login.pageTitle",
    defaultMessage: "Sign in · Numo9",
    description: "Browser tab title of the login page",
  },
});

export async function generateMetadata(): Promise<Metadata> {
  const fm = await getFormatMessage();
  return { title: fm(messages.title) };
}

/**
 * `/login` (A-02-T11). `?next=/o/acme/contacts` returns there after signing in; `?social=error`
 * is where a failed social sign-in lands (A-02-T16).
 */
export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { next, reset, social } = await searchParams;
  return (
    <AuthLayout>
      <LoginFlow
        next={typeof next === "string" ? next : undefined}
        notice={reset === "done" ? "resetDone" : social === "error" ? "socialError" : undefined}
      />
    </AuthLayout>
  );
}
