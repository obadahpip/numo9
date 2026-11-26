import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ExpenseClaimForm } from "@/purchases/expenses/ExpenseClaimForm";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
}

/** Purchases → new expense claim (E-04-T09): the claimant's form, phone first. */
export default async function NewExpenseClaimPage({ params }: { params: Promise<Params> }) {
  const { org } = await params;
  if (!ORG_SLUG.test(org)) notFound();
  return (
    <AppShell org={org} modulePath="purchases/expense-claims">
      <ExpenseClaimForm org={org} />
    </AppShell>
  );
}
