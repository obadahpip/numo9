"use client";

/**
 * The posting preview drawer (D-03a-T14): the journal approval will post (a draft) or posted
 * (an approved invoice) — Dr Accounts receivable, Cr each revenue account, Cr each tax control
 * account separately — with its totals. What it shows for a draft is what posts: the server
 * posts the preview's own lines (D-03a-T03).
 */
import { Drawer, SkeletonText, formatMoney, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { invoicesApi, type InvoicePreview } from "./api";
import { im } from "./messages";

export interface PostingPreviewDrawerProps {
  org: string;
  id: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const cents = (value: string) => Math.round(Number(value) * 100);

export function PostingPreviewDrawer({ org, id, open, onOpenChange }: PostingPreviewDrawerProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [preview, setPreview] = useState<InvoicePreview | null>(null);

  useEffect(() => {
    if (!open || !id) return;
    let live = true;
    setPreview(null);
    void invoicesApi.preview(org, id).then((answer) => {
      if (live && answer.status === 200) setPreview(answer.body);
    });
    return () => {
      live = false;
    };
  }, [org, id, open]);

  const journal = preview?.journal;
  const money = (value: number) => formatMoney((value / 100).toFixed(2), { locale });
  const debit = (journal?.lines ?? []).reduce((sum, row) => sum + cents(row.debit), 0);
  const credit = (journal?.lines ?? []).reduce((sum, row) => sum + cents(row.credit), 0);

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={fm(im.postingTitle, { posted: String(Boolean(journal?.posted)) })}
      description={fm(im.postingIntro)}
      closeLabel={fm(im.close)}
      size="lg"
    >
      {!journal ? (
        <SkeletonText lines={4} />
      ) : !journal.complete ? (
        <p role="alert" className="text-sm text-fg-danger">
          {journal.problem ?? fm(im.postingIncomplete)}
        </p>
      ) : (
        <table className="w-full text-sm" data-posting-preview="">
          <thead>
            <tr className="text-fg-muted">
              <th className="py-1 text-start font-medium">{fm(im.account)}</th>
              <th className="py-1 text-end font-medium">{fm(im.debit)}</th>
              <th className="py-1 text-end font-medium">{fm(im.credit)}</th>
            </tr>
          </thead>
          <tbody>
            {journal.lines.map((row, index) => (
              <tr key={`${row.account}-${index}`} className="border-t border-border" data-row="">
                <td className="py-1">
                  {fm(im.accountName, { code: row.account, name: row.name })}
                </td>
                <td className="py-1 text-end tabular-nums">
                  {cents(row.debit) ? money(cents(row.debit)) : ""}
                </td>
                <td className="py-1 text-end tabular-nums">
                  {cents(row.credit) ? money(cents(row.credit)) : ""}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-border font-semibold">
              <td className="py-1">{fm(im.totalRow)}</td>
              <td className="py-1 text-end tabular-nums">{money(debit)}</td>
              <td className="py-1 text-end tabular-nums">{money(credit)}</td>
            </tr>
          </tfoot>
        </table>
      )}
    </Drawer>
  );
}
