"use client";

/** The documents behind a line of the return, in a drawer (G-03-T11). */
import { Drawer, SkeletonText, formatDate, formatMoney, type AppLocale } from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { returnsApi, type DrillDocument, type ReturnLine } from "./api";
import { retm } from "./messages";

export interface LineDrillDrawerProps {
  org: string;
  returnId: string;
  line: ReturnLine | null;
  onClose: () => void;
}

export function LineDrillDrawer({ org, returnId, line, onClose }: LineDrillDrawerProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [documents, setDocuments] = useState<DrillDocument[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!line) return;
    let live = true;
    setDocuments(null);
    setFailed(false);
    void returnsApi.drill(org, returnId, line.line).then((answer) => {
      if (!live) return;
      if (answer.status === 200) setDocuments(answer.body.documents);
      else setFailed(true);
    });
    return () => {
      live = false;
    };
  }, [org, returnId, line]);

  const money = (value: string) => formatMoney(value, { locale });
  const total = (documents ?? []).reduce((sum, d) => sum + Math.round(Number(d.amount) * 100), 0);

  return (
    <Drawer
      open={line !== null}
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={line ? fm(retm.drillTitle, { line: line.line, label: line.label }) : ""}
      description={fm(retm.drillIntro)}
      closeLabel={fm(retm.close)}
      size="lg"
    >
      {failed ? (
        <p role="alert" className="text-sm text-fg-danger">
          {fm(retm.loadFailed)}
        </p>
      ) : documents === null ? (
        <SkeletonText lines={4} />
      ) : documents.length === 0 ? (
        <p className="text-sm text-fg-muted">{fm(retm.drillEmpty)}</p>
      ) : (
        <table className="w-full text-sm" data-testid="drill-documents">
          <thead>
            <tr className="text-start text-fg-muted">
              <th className="py-1 text-start font-medium">{fm(retm.date)}</th>
              <th className="py-1 text-start font-medium">{fm(retm.document)}</th>
              <th className="py-1 text-start font-medium">{fm(retm.contact)}</th>
              <th className="py-1 text-end font-medium">{fm(retm.amount)}</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={`${doc.entry}-${doc.number}`} className="border-t border-border">
                <td className="py-1">{formatDate(doc.date, { locale })}</td>
                <td className="py-1">
                  {doc.url ? <Link href={doc.url}>{doc.number}</Link> : doc.number}
                  {doc.detail?.filed_period ? (
                    <span className="block text-xs text-fg-muted">
                      {fm(retm.lateAdjustment, { period: doc.detail.filed_period })}
                    </span>
                  ) : null}
                </td>
                <td className="py-1">{doc.contact ?? ""}</td>
                <td className="py-1 text-end tabular-nums">{money(doc.amount)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-border font-semibold">
              <td className="py-1" colSpan={3}>
                {fm(retm.drillTotal)}
              </td>
              <td className="py-1 text-end tabular-nums">{money((total / 100).toFixed(2))}</td>
            </tr>
          </tfoot>
        </table>
      )}
    </Drawer>
  );
}
