import { notFound } from "next/navigation";

import { AppShell } from "@/components/AppShell";
import { ExpenseClaimForm } from "@/purchases/expenses/ExpenseClaimForm";
import { ORG_SLUG } from "@/routing/routes";

interface Params {
  org: string;
  id: string;
}

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Purchases → edit a draft or rejected expense claim (E-04-T09). */
export default async function EditExpenseClaimPage({ params }: { params: Promise<Params> }) {
  const { org, id } = await params;
  if (!ORG_SLUG.test(org) || !ID.test(id)) notFound();
  return (
    <AppShell org={org} modulePath="purchases/expense-claims">
      <ExpenseClaimForm org={org} id={id} />
    </AppShell>
  );
}
