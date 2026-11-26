"use client";

/** The invoice page (D-03a-T13, T14, T16): the editor with its period ribbon, action bar and
 * credit-limit check. */
import { useRouter } from "next/navigation";

import { CreditLimitCheck } from "../CreditLimitBanner";
import { InvoiceActionBar } from "./InvoiceActionBar";
import { InvoiceEditor } from "./InvoiceEditor";
import { PeriodRibbon } from "./PeriodRibbon";

export function InvoiceScreen({ org, id }: { org: string; id?: string }) {
  const router = useRouter();
  const navigate = (href: string) => router.replace(href);
  return (
    <InvoiceEditor
      org={org}
      id={id}
      navigate={navigate}
      ribbon={(invoice, _date, refresh) => (
        <PeriodRibbon org={org} id={invoice?.id ?? null} refresh={refresh} />
      )}
      actions={(context) => <InvoiceActionBar org={org} context={context} navigate={navigate} />}
      banners={(invoice, refresh) =>
        invoice && invoice.status === "draft" ? (
          <CreditLimitCheck org={org} id={invoice.id} version={refresh} />
        ) : null
      }
    />
  );
}
