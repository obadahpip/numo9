import type { Metadata } from "next";

import { AuthLayout } from "@/auth/AuthLayout";
import { TwoFactorPage } from "@/auth/TwoFactorPage";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";

const messages = defineMessages({
  title: {
    id: "auth.twoFactor.pageTitle",
    defaultMessage: "Authentication code · Numo9",
    description: "Browser tab title of the 2FA page",
  },
});

export async function generateMetadata(): Promise<Metadata> {
  const fm = await getFormatMessage();
  return { title: fm(messages.title) };
}

/** `/2fa` (A-02-T11): the code step of a sign-in waiting in this browser's session. */
export default async function TwoFactorRoute({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { next } = await searchParams;
  return (
    <AuthLayout>
      <TwoFactorPage next={typeof next === "string" ? next : undefined} />
    </AuthLayout>
  );
}
