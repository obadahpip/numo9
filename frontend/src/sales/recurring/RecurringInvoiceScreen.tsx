"use client";

/** The recurring invoice page (D-04-T08, T09): the template editor with the preview of its
 * next invoice. */
import { useRouter } from "next/navigation";

import { RecurringInvoiceEditor } from "./RecurringInvoiceEditor";
import { RecurringPreview } from "./RecurringPreview";

export function RecurringInvoiceScreen({ org, id }: { org: string; id?: string }) {
  const router = useRouter();
  return (
    <RecurringInvoiceEditor
      org={org}
      id={id}
      navigate={(href) => router.replace(href)}
      aside={(template, refresh) => (
        <RecurringPreview org={org} id={template.id} refresh={refresh} />
      )}
    />
  );
}
