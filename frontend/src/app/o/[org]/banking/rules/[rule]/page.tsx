import { notFound } from "next/navigation";

import { RuleEditor } from "@/banking/rules/RuleEditor";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
  rule: string;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Edit a bank rule (F-04-T11), `/o/:org/banking/rules/<rule id>`. */
export default async function BankRulePage({ params }: { params: Promise<Params> }) {
  const { org, rule } = await params;
  if (!ORG_SLUG.test(org) || !UUID.test(rule)) notFound();
  return (
    <AppShell org={org} modulePath="banking">
      <RuleEditor org={org} id={rule} />
    </AppShell>
  );
}
