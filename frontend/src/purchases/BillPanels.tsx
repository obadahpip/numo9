"use client";

/** The bill editor's side panels (E-02-T12…T14), refreshed after every save. */
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { billsApi, type Bill, type BillPreview } from "./api";
import { DuplicatePanel } from "./DuplicatePanel";
import { MatchPanel } from "./MatchPanel";
import { routing as r } from "./messages";

export function BillPanels({
  org,
  bill,
  refresh,
}: {
  org: string;
  bill: Bill | null;
  refresh: number;
}) {
  const fm = useFormatMessage();
  const [preview, setPreview] = useState<BillPreview | null>(null);
  useEffect(() => {
    setPreview(null);
    if (!bill) return;
    let cancelled = false;
    void billsApi.preview(org, bill.id).then((result) => {
      if (!cancelled && result.status === 200 && Array.isArray(result.body.duplicates))
        setPreview(result.body);
    });
    return () => {
      cancelled = true;
    };
  }, [org, bill, refresh]);
  if (!preview || !bill) return null;
  return (
    <div className="flex flex-col gap-3" data-bill-panels="">
      <section
        aria-labelledby="bill-routing"
        className="rounded-md border border-border bg-surface-subtle p-3 text-sm"
        data-routing={preview.routing.rule ?? ""}
      >
        <h2 id="bill-routing" className="font-semibold text-fg">
          {fm(r.title)}
        </h2>
        <p className="text-fg">{preview.routing.explanation || fm(r.noRule)}</p>
      </section>
      <MatchPanel rows={preview.match} />
      <DuplicatePanel org={org} suspects={preview.duplicates} />
    </div>
  );
}
