"use client";

/**
 * The invoice action bar (D-03a-T14): the actions of `actionMatrix.ts` for the invoice's status —
 * Save draft / Approve (Submit for approval when the approval rule applies) / Delete on a draft;
 * Approve and post when awaiting approval; Email, PDF, Copy, Copy to quote and Void once posted —
 * and Preview posting, the drawer with the journal (D-03a-T14). Approve saves first, so what was
 * on screen is what posts.
 */
import { Button, Dialog, Input } from "@numo9/ui";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { invoiceActions } from "./actionMatrix";
import { invoiceUrl, invoicesApi, type Invoice } from "./api";
import type { InvoiceActionContext } from "./InvoiceEditor";
import { im } from "./messages";
import { PostingPreviewDrawer } from "./PostingPreviewDrawer";

export interface InvoiceActionBarProps {
  org: string;
  context: InvoiceActionContext;
  navigate: (href: string) => void;
}

export function InvoiceActionBar({ org, context, navigate }: InvoiceActionBarProps) {
  const fm = useFormatMessage();
  const { invoice, busy, ready } = context;
  const [needsApproval, setNeedsApproval] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [voiding, setVoiding] = useState(false);
  const [voidDate, setVoidDate] = useState("");
  const [voidReason, setVoidReason] = useState("");

  useEffect(() => {
    if (!invoice || invoice.status !== "draft") return setNeedsApproval(false);
    let live = true;
    void invoicesApi.preview(org, invoice.id).then((answer) => {
      if (live && answer.status === 200) setNeedsApproval(Boolean(answer.body.approval));
    });
    return () => {
      live = false;
    };
  }, [org, invoice]);

  const actions = invoiceActions(invoice?.status ?? "new", { needsApproval });
  const has = (action: (typeof actions)[number]) => actions.includes(action);

  async function run(
    work: (saved: Invoice) => ReturnType<typeof invoicesApi.approve>,
    done: (result: Invoice) => string,
    { saveFirst = true }: { saveFirst?: boolean } = {},
  ) {
    if (busy) return;
    context.setBusy(true);
    const fresh = !invoice;
    const saved = saveFirst ? await context.save(true) : invoice;
    if (saved) {
      const result = await work(saved);
      if (result.status === 200) context.show(result.body, done(result.body));
      else context.refuse(result.body ?? {});
      if (fresh) context.open(saved);
    }
    context.setBusy(false);
  }

  async function preview() {
    if (!invoice) {
      if (busy) return;
      context.setBusy(true);
      const saved = await context.save();
      context.setBusy(false);
      if (!saved) return;
    }
    setPreviewing(true);
  }

  async function copy(to: "invoice" | "quote") {
    if (!invoice || busy) return;
    context.setBusy(true);
    const result = await invoicesApi.copy(org, invoice.id, to);
    context.setBusy(false);
    if (result.status !== 201) return context.refuse(result.body ?? {});
    const made = result.body;
    navigate("url" in made && to === "quote" ? made.url : invoiceUrl(org, made.id));
  }

  async function remove() {
    if (!invoice || busy) return;
    const result = await invoicesApi.remove(org, invoice.id);
    if (result.status === 204) navigate(`/o/${org}/sales/invoices/new`);
    else context.refuse(result.body ?? {});
  }

  return (
    <div
      role="toolbar"
      aria-label={fm(im.actions)}
      className="flex flex-wrap items-center gap-3"
      data-invoice-actions={actions.join(" ")}
    >
      {has("save") ? (
        <Button type="submit" disabled={busy || !ready}>
          {busy ? fm(im.saving) : fm(im.saveDraft)}
        </Button>
      ) : null}
      {has("approve") ? (
        <Button
          variant="primary"
          disabled={busy || !ready}
          onClick={() =>
            void run(
              (saved) => invoicesApi.approve(org, saved.id),
              (done) =>
                done.status === "awaiting_approval"
                  ? fm(im.submitted)
                  : fm(im.approved, { number: done.number }),
            )
          }
        >
          {fm(im.approve)}
        </Button>
      ) : null}
      {has("submit") ? (
        <Button
          variant="primary"
          disabled={busy || !ready}
          onClick={() =>
            void run(
              (saved) => invoicesApi.approve(org, saved.id),
              () => fm(im.submitted),
            )
          }
        >
          {fm(im.submitForApproval)}
        </Button>
      ) : null}
      {has("approve_waiting") ? (
        <Button
          variant="primary"
          disabled={busy}
          onClick={() =>
            void run(
              (saved) => invoicesApi.approve(org, saved.id),
              (done) => fm(im.approved, { number: done.number }),
              { saveFirst: false },
            )
          }
        >
          {fm(im.approveWaiting)}
        </Button>
      ) : null}
      {has("email") && invoice ? (
        <Button asChild>
          <Link href={`${invoiceUrl(org, invoice.id)}/email`}>{fm(im.email)}</Link>
        </Button>
      ) : null}
      {has("pdf") && invoice ? (
        <Button asChild>
          <a href={invoice.pdf} target="_blank" rel="noreferrer">
            {fm(im.pdf)}
          </a>
        </Button>
      ) : null}
      {has("copy") ? (
        <Button disabled={busy} onClick={() => void copy("invoice")}>
          {fm(im.copy)}
        </Button>
      ) : null}
      {has("copy_quote") ? (
        <Button disabled={busy} onClick={() => void copy("quote")}>
          {fm(im.copyToQuote)}
        </Button>
      ) : null}
      {has("preview") ? (
        <Button
          variant="ghost"
          disabled={busy || (!invoice && !ready)}
          onClick={() => void preview()}
        >
          {fm(im.previewPosting)}
        </Button>
      ) : null}
      {has("delete") ? (
        <Button variant="danger" disabled={busy} onClick={() => void remove()}>
          {fm(im.delete)}
        </Button>
      ) : null}
      {has("void") && invoice ? (
        <Button variant="danger" disabled={busy} onClick={() => setVoiding(true)}>
          {fm(im.void)}
        </Button>
      ) : null}

      <PostingPreviewDrawer
        org={org}
        id={invoice?.id ?? null}
        open={previewing}
        onOpenChange={setPreviewing}
      />
      {invoice ? (
        <Dialog
          open={voiding}
          onOpenChange={setVoiding}
          title={fm(im.voidTitle, { number: invoice.number })}
          description={fm(im.voidIntro)}
          closeLabel={fm(im.close)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setVoiding(false)}>
                {fm(im.cancel)}
              </Button>
              <Button
                variant="danger"
                loading={busy}
                onClick={() => {
                  setVoiding(false);
                  void run(
                    (saved) =>
                      invoicesApi.void(org, saved.id, {
                        ...(voidDate ? { date: voidDate } : {}),
                        reason: voidReason,
                      }),
                    () => fm(im.voided),
                    { saveFirst: false },
                  );
                }}
              >
                {fm(im.void)}
              </Button>
            </>
          }
        >
          <div className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-sm font-medium">
              {fm(im.voidDate)}
              <Input type="date" value={voidDate} onChange={(e) => setVoidDate(e.target.value)} />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium">
              {fm(im.voidReason)}
              <Input value={voidReason} onChange={(e) => setVoidReason(e.target.value)} />
            </label>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}
