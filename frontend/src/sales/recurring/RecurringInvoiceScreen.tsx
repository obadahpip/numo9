"use client";

/** The recurring invoice page (D-04-T08): the template editor. */
import { useRouter } from "next/navigation";

import { RecurringInvoiceEditor } from "./RecurringInvoiceEditor";

export function RecurringInvoiceScreen({ org, id }: { org: string; id?: string }) {
  const router = useRouter();
  return <RecurringInvoiceEditor org={org} id={id} navigate={(href) => router.replace(href)} />;
}
