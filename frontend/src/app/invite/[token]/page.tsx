import type { Metadata } from "next";

import { AuthLayout } from "@/auth/AuthLayout";
import { InviteAccept } from "@/auth/InviteAccept";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";

const messages = defineMessages({
  title: {
    id: "auth.invite.pageTitle",
    defaultMessage: "Invitation · Numo9",
    description: "Browser tab title of the invitation page",
  },
});

export async function generateMetadata(): Promise<Metadata> {
  const fm = await getFormatMessage();
  return { title: fm(messages.title), referrer: "no-referrer" };
}

/**
 * `/invite/<token>` (A-02-T12): the link in an invitation email. The token goes to the API in
 * request bodies only; `no-referrer` keeps it out of other sites' logs.
 */
export default async function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return (
    <AuthLayout>
      <InviteAccept token={decodeURIComponent(token)} />
    </AuthLayout>
  );
}
