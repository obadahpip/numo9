"use client";

/**
 * The quote action bar (D-02-T12): the actions of `actionMatrix.ts` for the quote's status — Save
 * draft, Email to customer / Mark as sent (both save first, so what was on screen is what is
 * sent), Copy link / Withdraw links, Mark accepted / declined (the customer answered another
 * way), Convert to invoice (identical lines, deposit deducted), Revise (a new version that
 * supersedes this one), PDF, Copy, Delete draft.
 */
import { Button, Dialog, Input } from "@numo9/ui";
import { useState } from "react";

import { useFormatMessage } from "@/i18n";

import type { Refusal } from "../invoices/api";
import { quoteActions, type QuoteAction } from "./actionMatrix";
import { quoteUrl, quotesApi, type Quote } from "./api";
import type { QuoteActionContext } from "./QuoteEditor";
import { qm } from "./messages";

export interface QuoteActionBarProps {
  org: string;
  context: QuoteActionContext;
  navigate: (href: string) => void;
}

type Answer = Promise<{ status: number; body: (Quote & Refusal) | Refusal }>;

export function QuoteActionBar({ org, context, navigate }: QuoteActionBarProps) {
  const fm = useFormatMessage();
  const { quote, busy, ready } = context;
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState("");
  const actions = quoteActions(quote?.status ?? "new");
  const has = (action: QuoteAction) => actions.includes(action);

  async function run(work: (saved: Quote) => Answer, notice: string, saveFirst = false) {
    if (busy) return;
    context.setBusy(true);
    const fresh = !quote;
    const saved = saveFirst || fresh ? await context.save(true) : quote;
    if (saved) {
      const result = await work(saved);
      if (result.status === 200 && "id" in result.body) {
        context.show(result.body as Quote, notice);
      } else context.refuse(result.body ?? {});
      if (fresh) context.open(saved);
    }
    context.setBusy(false);
  }

  async function go(
    work: () => Promise<{ status: number; body: unknown }>,
    href: (b: never) => string,
  ) {
    if (busy) return;
    context.setBusy(true);
    const result = await work();
    context.setBusy(false);
    if (result.status === 201) navigate(href(result.body as never));
    else context.refuse((result.body as Refusal) ?? {});
  }

  async function copyLink() {
    if (!quote || busy) return;
    let url = quote.link?.url;
    if (!url) {
      const made = await quotesApi.link(org, quote.id);
      if (made.status !== 200) return context.refuse(made.body ?? {});
      context.show(made.body);
      url = made.body.link?.url;
    }
    if (url) {
      await navigator.clipboard?.writeText(url).catch(() => undefined);
      context.notify(fm(qm.linkCopied));
    }
  }

  async function remove() {
    if (!quote || busy) return;
    const result = await quotesApi.remove(org, quote.id);
    if (result.status === 204) navigate(`/o/${org}/sales/quotes`);
    else context.refuse(result.body ?? {});
  }

  return (
    <div
      role="toolbar"
      aria-label={fm(qm.actions)}
      className="flex flex-wrap items-center gap-3"
      data-quote-actions={actions.join(" ")}
    >
      {has("save") ? (
        <Button type="submit" disabled={busy || !ready}>
          {busy ? fm(qm.saving) : fm(qm.saveDraft)}
        </Button>
      ) : null}
      {has("send") ? (
        <Button
          variant="primary"
          disabled={busy || !ready}
          onClick={() =>
            void run(
              (saved) => quotesApi.send(org, saved.id, {}),
              fm(qm.sent),
              saveBeforeSending(quote),
            )
          }
        >
          {fm(qm.send)}
        </Button>
      ) : null}
      {has("mark_sent") ? (
        <Button
          disabled={busy || !ready}
          onClick={() =>
            void run(
              (saved) => quotesApi.send(org, saved.id, { email: false }),
              fm(qm.markedSent),
              true,
            )
          }
        >
          {fm(qm.markSent)}
        </Button>
      ) : null}
      {has("copy_link") ? (
        <Button disabled={busy} onClick={() => void copyLink()}>
          {fm(qm.copyLink)}
        </Button>
      ) : null}
      {has("accept") ? (
        <Button
          disabled={busy}
          onClick={() => void run((saved) => quotesApi.accept(org, saved.id), fm(qm.accepted))}
        >
          {fm(qm.accept)}
        </Button>
      ) : null}
      {has("decline") ? (
        <Button disabled={busy} onClick={() => setDeclining(true)}>
          {fm(qm.decline)}
        </Button>
      ) : null}
      {has("convert") && quote ? (
        <Button
          variant="primary"
          disabled={busy}
          onClick={() =>
            void go(
              () => quotesApi.invoice(org, quote.id),
              (made: { url: string }) => made.url,
            )
          }
        >
          {fm(qm.convert)}
        </Button>
      ) : null}
      {has("revise") && quote ? (
        <Button
          disabled={busy}
          onClick={() =>
            void go(
              () => quotesApi.revise(org, quote.id),
              (made: { id: string }) => quoteUrl(org, made.id),
            )
          }
        >
          {fm(qm.revise)}
        </Button>
      ) : null}
      {has("pdf") && quote ? (
        <Button asChild>
          <a href={quote.pdf} target="_blank" rel="noreferrer">
            {fm(qm.pdf)}
          </a>
        </Button>
      ) : null}
      {has("copy") && quote ? (
        <Button
          disabled={busy}
          onClick={() =>
            void go(
              () => quotesApi.copy(org, quote.id, "quote"),
              (made: { id: string }) => quoteUrl(org, made.id),
            )
          }
        >
          {fm(qm.copy)}
        </Button>
      ) : null}
      {has("revoke_links") && quote?.link ? (
        <Button
          variant="ghost"
          disabled={busy}
          onClick={() =>
            void run((saved) => quotesApi.revokeLinks(org, saved.id), fm(qm.linksRevoked))
          }
        >
          {fm(qm.revokeLinks)}
        </Button>
      ) : null}
      {has("delete") ? (
        <Button variant="danger" disabled={busy} onClick={() => void remove()}>
          {fm(qm.delete)}
        </Button>
      ) : null}

      {quote ? (
        <Dialog
          open={declining}
          onOpenChange={setDeclining}
          title={fm(qm.decline)}
          closeLabel={fm(qm.cancel)}
          footer={
            <>
              <Button variant="ghost" onClick={() => setDeclining(false)}>
                {fm(qm.cancel)}
              </Button>
              <Button
                variant="danger"
                loading={busy}
                onClick={() => {
                  setDeclining(false);
                  void run((saved) => quotesApi.decline(org, saved.id, reason), "");
                }}
              >
                {fm(qm.confirmDecline)}
              </Button>
            </>
          }
        >
          <label className="flex flex-col gap-1 text-sm font-medium">
            {fm(qm.declineReason)}
            <Input value={reason} onChange={(e) => setReason(e.target.value)} />
          </label>
        </Dialog>
      ) : null}
    </div>
  );
}

/** A draft is saved before it is emailed; a sent quote is re-sent as it is. */
function saveBeforeSending(quote: Quote | null): boolean {
  return !quote || quote.status === "draft";
}
