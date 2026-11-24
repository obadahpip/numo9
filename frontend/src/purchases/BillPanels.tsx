"use client";

/** The bill editor's side panels (E-02-T12…T14), refreshed after every save. */
import { useEffect, useState } from "react";

import { billsApi, type Bill, type BillPreview } from "./api";
import { DuplicatePanel } from "./DuplicatePanel";

export function BillPanels({
  org,
  bill,
  refresh,
}: {
  org: string;
  bill: Bill | null;
  refresh: number;
}) {
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
      <DuplicatePanel org={org} suspects={preview.duplicates} />
    </div>
  );
}
