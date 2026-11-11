import type { Metadata } from "next";

import { AuthLayout } from "@/auth/AuthLayout";
import { ResetPassword } from "@/auth/ResetPassword";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";

const messages = defineMessages({
  title: {
    id: "auth.reset.pageTitle",
    defaultMessage: "Reset your password · Numo9",
    description: "Browser tab title of the password reset pages",
  },
});

export async function generateMetadata(): Promise<Metadata> {
  const fm = await getFormatMessage();
  return { title: fm(messages.title), referrer: "no-referrer" };
}

/**
 * `/reset/<key>` (A-02-T11): the link from the reset email (`HEADLESS_FRONTEND_URLS`). The key
 * goes to the API in a header/body only; `no-referrer` keeps it out of other sites' logs.
 */
export default async function ResetPasswordPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  return (
    <AuthLayout>
      <ResetPassword resetKey={decodeURIComponent(key)} />
    </AuthLayout>
  );
}
