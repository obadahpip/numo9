import { notFound } from "next/navigation";

import type { RuleType } from "@/banking/rules/api";
import { RuleEditor } from "@/banking/rules/RuleEditor";
import { AppShell } from "@/components/AppShell";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

const TYPES: readonly string[] = ["spend", "receive", "transfer"];

/** New bank rule (F-04-T11), `/o/:org/banking/rules/new?type=spend|receive|transfer`. */
export default async function NewBankRulePage({
  params,
  searchParams,
}: {
  params: Promise<Params>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { org } = await params;
  const query = await searchParams;
  if (!ORG_SLUG.test(org)) notFound();
  const type = (query.type && TYPES.includes(query.type) ? query.type : "spend") as RuleType;
  return (
    <AppShell org={org} modulePath="banking">
      <RuleEditor org={org} type={type} />
    </AppShell>
  );
}
