"use client";

/**
 * Merge dialog (B-01-T17): the two contacts side by side with a choice per field, how many
 * records of each kind move to the surviving contact (and which stay on the alias because they're
 * posted), then one merge (B-01-T12 — one transaction; the history stays visible on the survivor).
 */
import { Button, Dialog, RadioGroup } from "@numo9/ui";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { contactsApi, firstError, type ContactDetail, type MergeRecords } from "./api";
import { fmsg } from "./formMessages";

const CHOOSABLE = ["display_name", "legal_name", "bn", "currency", "credit_limit"] as const;

export function MergeDialog({
  org,
  survivorId,
  mergedId,
  onClose,
  onMerged,
}: {
  org: string;
  survivorId: string;
  mergedId: string;
  onClose: () => void;
  onMerged: (survivor: ContactDetail, message: string) => void;
}) {
  const fm = useFormatMessage();
  const [pair, setPair] = useState<{ survivor: ContactDetail; merged: ContactDetail } | null>(null);
  const [records, setRecords] = useState<MergeRecords[]>([]);
  const [choice, setChoice] = useState<Record<string, "survivor" | "merged">>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void contactsApi.mergePreview(org, survivorId, mergedId).then((result) => {
      if (result.status === 200) {
        setPair({ survivor: result.body.survivor, merged: result.body.merged });
        setRecords(result.body.records);
      } else {
        setError(firstError(result.body) ?? "");
      }
    });
  }, [org, survivorId, mergedId]);

  const labels: Record<(typeof CHOOSABLE)[number], string> = {
    display_name: fm(fmsg.displayName),
    legal_name: fm(fmsg.legalName),
    bn: fm(fmsg.bn),
    currency: fm(fmsg.currency),
    credit_limit: fm(fmsg.creditLimit),
  };
  const survivorName = pair?.survivor.display_name ?? "";
  const mergedName = pair?.merged.display_name ?? "";

  const merge = async () => {
    setBusy(true);
    const sources = Object.fromEntries(
      Object.entries(choice).filter(([, side]) => side === "merged"),
    );
    const result = await contactsApi.merge(org, survivorId, mergedId, sources);
    setBusy(false);
    if (result.status === 200) {
      onMerged(
        result.body.survivor,
        fm(fmsg.mergeDone, { merged: mergedName, survivor: result.body.survivor.display_name }),
      );
    } else {
      setError(firstError(result.body) ?? "");
    }
  };

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={fm(fmsg.mergeTitle, { merged: mergedName, survivor: survivorName })}
      description={fm(fmsg.mergeIntro, { merged: mergedName })}
      closeLabel={fm(fmsg.mergeClose)}
      size="lg"
      footer={
        <>
          <Button onClick={onClose}>{fm(fmsg.mergeCancel)}</Button>
          <Button variant="primary" disabled={busy || !pair} onClick={() => void merge()}>
            {fm(fmsg.mergeConfirm)}
          </Button>
        </>
      }
    >
      {pair ? (
        <div className="flex flex-col gap-4">
          <ul className="flex flex-col gap-3">
            {CHOOSABLE.map((field) => {
              const show = (value: unknown) =>
                value === null || value === "" ? "—" : String(value);
              return (
                <li key={field} className="flex flex-col gap-1">
                  <span className="text-sm font-semibold">{labels[field]}</span>
                  <RadioGroup
                    aria-label={fm(fmsg.keepFrom, { field: labels[field] })}
                    value={choice[field] ?? "survivor"}
                    onValueChange={(value) =>
                      setChoice((current) => ({
                        ...current,
                        [field]: value as "survivor" | "merged",
                      }))
                    }
                    options={[
                      { value: "survivor", label: show(pair.survivor[field]) },
                      { value: "merged", label: show(pair.merged[field]) },
                    ]}
                    className="flex flex-wrap gap-4"
                  />
                </li>
              );
            })}
          </ul>
          <ul className="flex flex-col gap-1 text-sm" data-merge-preview="">
            {records.length === 0 ? <li>{fm(fmsg.mergeNothing)}</li> : null}
            {records.map((row) => (
              <li key={row.records}>
                {fm(row.moves ? fmsg.mergeMoves : fmsg.mergeKeeps, {
                  count: row.count,
                  records: row.records,
                  survivor: survivorName,
                })}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {error ? (
        <p role="alert" className="mt-3 text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
    </Dialog>
  );
}
