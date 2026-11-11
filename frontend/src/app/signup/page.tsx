import type { Metadata } from "next";

import { AuthLayout } from "@/auth/AuthLayout";
import { SignupFlow, type SignupPath } from "@/auth/SignupFlow";
import { defineMessages } from "@/i18n";
import { getFormatMessage } from "@/i18n/server";

const messages = defineMessages({
  title: {
    id: "auth.signup.pageTitle",
    defaultMessage: "Create your account · Numo9",
    description: "Browser tab title of the sign-up page",
  },
});

export async function generateMetadata(): Promise<Metadata> {
  const fm = await getFormatMessage();
  return { title: fm(messages.title) };
}

const PATHS: readonly SignupPath[] = ["accountant", "organisation"];

/**
 * `/signup` (A-02-T10). `?path=accountant` or `?path=organisation` (links from the public site)
 * skips the choice step; anything else starts at the choice.
 */
export default async function SignupPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { path } = await searchParams;
  const initialPath = PATHS.find((p) => p === path);
  return (
    <AuthLayout>
      <SignupFlow initialPath={initialPath} />
    </AuthLayout>
  );
}
