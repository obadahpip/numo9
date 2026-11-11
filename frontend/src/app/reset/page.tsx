import type { Metadata } from "next";

import { AuthLayout } from "@/auth/AuthLayout";
import { ResetRequest } from "@/auth/ResetRequest";
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
  return { title: fm(messages.title) };
}

/** `/reset` (A-02-T11): request a password reset link. */
export default function ResetRequestPage() {
  return (
    <AuthLayout>
      <ResetRequest />
    </AuthLayout>
  );
}
