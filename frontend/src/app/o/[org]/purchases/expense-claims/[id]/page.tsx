import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ExpenseClaimReview } from "@/purchases/expenses/ExpenseClaimReview";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
  id: string;
}

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Purchases → one expense claim, the approver's view (E-04-T11). */
export default async function ExpenseClaimPage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !ID.test(id)) notFound();
  return (
    <AppShell org={org} modulePath="purchases/expense-claims">
      <ExpenseClaimReview org={org} id={id} />
    </AppShell>
  );
}
