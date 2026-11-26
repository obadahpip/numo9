import type { Metadata } from "next";

import { AuthLayout } from "@/auth/AuthLayout";
import { getFormatMessage } from "@/i18n/server";
import { PublicQuote } from "@/sales/quotes/PublicQuote";
import { pm } from "@/sales/quotes/publicMessages";

export async function generateMetadata(): Promise<Metadata> {
  const fm = await getFormatMessage();
  return { title: fm(pm.pageTitle), referrer: "no-referrer", robots: { index: false } };
}

/**
 * `/q/<token>` (D-02-T13): the quote link of a quote email — no sign-in, the signed token is the
 * credential. `no-referrer` keeps the token out of other sites' logs.
 */
export default async function PublicQuotePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return (
    <AuthLayout wide>
      <PublicQuote token={decodeURIComponent(token)} />
    </AuthLayout>
  );
}
