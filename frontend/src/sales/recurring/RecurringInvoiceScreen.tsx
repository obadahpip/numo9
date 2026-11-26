"use client";

/** The recurring invoice page (D-04-T08…T10): the template editor with the preview of its next
 * invoice, and the history tab of the invoices it generated and the dates it skipped. */
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useFormatMessage } from "@/i18n";

import { RecurringHistory } from "./RecurringInvoiceList";
import { RecurringInvoiceEditor } from "./RecurringInvoiceEditor";
import { RecurringPreview } from "./RecurringPreview";
import { rim } from "./messages";

export function RecurringInvoiceScreen({ org, id }: { org: string; id?: string }) {
  const router = useRouter();
  const fm = useFormatMessage();
  const [tab, setTab] = useState<"template" | "history">("template");
  const editor = (
    <RecurringInvoiceEditor
      org={org}
      id={id}
      navigate={(href) => router.replace(href)}
      aside={(template, refresh) => (
        <RecurringPreview org={org} id={template.id} refresh={refresh} />
      )}
    />
  );
  if (!id) return editor;
  return (
    <div className="flex flex-col gap-4">
      <div role="tablist" aria-label={fm(rim.listTitle)} className="flex gap-1">
        {(["template", "history"] as const).map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
            className={`rounded-md px-3 py-1.5 text-sm ${
              tab === name ? "bg-surface-muted font-semibold text-fg" : "text-fg-muted"
            }`}
          >
            {fm(name === "template" ? rim.templateTab : rim.historyTab)}
          </button>
        ))}
      </div>
      {tab === "template" ? editor : <RecurringHistory org={org} id={id} />}
    </div>
  );
}
