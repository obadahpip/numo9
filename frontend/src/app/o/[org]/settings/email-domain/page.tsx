import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { EmailDomainScreen } from "@/email-domains/EmailDomainScreen";
import { ORG_SLUG } from "@/routing/routes";
import { SettingsLayout } from "@/settings/SettingsLayout";

interface Params {
  org: string;
}

/** Settings → Email domain (A-07-T10), `/o/:org/settings/email-domain`. */
export default async function EmailDomainPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="settings/email-domain">
      <SettingsLayout org={org} section="settings/email-domain">
        <EmailDomainScreen org={org} />
      </SettingsLayout>
    </AppShell>
  );
}
