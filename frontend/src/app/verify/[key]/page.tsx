import type { Metadata } from "next";

import { AuthLayout } from "@/auth/AuthLayout";
import { VerifyEmail } from "@/auth/VerifyEmail";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";

const messages = defineMessages({
  title: {
    id: "auth.verify.pageTitle",
    defaultMessage: "Verify your email · Numo9",
    description: "Browser tab title of the email verification page",
  },
});

export async function generateMetadata(): Promise<Metadata> {
  const fm = await getFormatMessage();
  return { title: fm(messages.title), referrer: "no-referrer" };
}

/**
 * `/verify/<key>` (A-02-T10): the link in the verification email (`HEADLESS_FRONTEND_URLS`).
 * The key goes to the API in the request body; `no-referrer` keeps it out of other sites' logs.
 */
export default async function VerifyPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  return (
    <AuthLayout>
      <VerifyEmail verificationKey={decodeURIComponent(key)} />
    </AuthLayout>
  );
}
