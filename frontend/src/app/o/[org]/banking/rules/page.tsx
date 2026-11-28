import { notFound } from "next/navigation";

import { RulesList } from "@/banking/rules/RulesList";
import type { RuleType } from "@/banking/rules/api";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

const TYPES: readonly string[] = ["spend", "receive", "transfer"];

/** Bank rules (F-04-T10), `/o/:org/banking/rules?type=spend|receive|transfer`. */
export default async function BankRulesPage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<{ type?: string }>;
}) {
  const { org } = await params;
  const { type } = await searchParams;
  if (!ORG_SLUG.test(org)) notFound();
  const initial = (type && TYPES.includes(type) ? type : "spend") as RuleType;
  return (
    <AppShell org={org} modulePath="banking">
      <RulesList org={org} initialType={initial} />
    </AppShell>
  );
}
