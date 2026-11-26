"use client";

/** The invoice page (D-03a-T13, T14, T16): the editor with its credit-limit banner. */
import { useRouter } from "next/navigation";

import { CreditLimitCheck } from "../CreditLimitBanner";
import { InvoiceEditor } from "./InvoiceEditor";

export function InvoiceScreen({ org, id }: { org: string; id?: string }) {
  const router = useRouter();
  return (
    <InvoiceEditor
      org={org}
      id={id}
      navigate={(href) => router.replace(href)}
      banners={(invoice, refresh) =>
        invoice && invoice.status === "draft" ? (
          <CreditLimitCheck org={org} id={invoice.id} version={refresh} />
        ) : null
      }
    />
  );
}
