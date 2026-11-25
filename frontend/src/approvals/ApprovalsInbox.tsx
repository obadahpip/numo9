"use client";

/**
 * Approvals inbox (C-04-T12), `/o/:org/approvals`: everything waiting for approval that the
 * person may approve or submitted (C-04-T08), oldest first, with a side preview of the selected
 * item (its lines) and a limit indicator ("Your limit $5,000.00"). Keyboard: ↑/↓ choose, **A**
 * approves, **R** sends back (a reason is asked). Items the person created say "You created
 * this" and have no Approve button — the server refuses self-approval anyway.
 */
import {
  Badge,
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  formatDate,
  formatMoney,
  type AppLocale,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState, type KeyboardEvent } from "react";

import { useFormatMessage } from "@/i18n";
import { getJournal, type Journal } from "@/journals/api";
import { writeApi } from "@/journals/write/api";
import { expenseClaimsApi } from "@/purchases/expenses/api";

import { approvalsApi, type ApprovalItem, type ApprovalsInbox as Inbox } from "./api";
import { im } from "./messages";

const MIN_REASON = 3;

export function ApprovalsInbox({ org }: Readonly<{ org: string }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [inbox, setInbox] = useState<Inbox | null>(null);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState(0);
  const [preview, setPreview] = useState<Journal | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<ApprovalItem | null>(null);
  const [reason, setReason] = useState("");

  const load = useCallback(
    () =>
      approvalsApi
        .inbox(org)
        .then((r) => {
          if (r.status !== 200) return setFailed(true);
          setInbox(r.body);
          setSelected((i) => Math.min(i, Math.max(0, r.body.results.length - 1)));
        })
        .catch(() => setFailed(true)),
    [org],
  );
  useEffect(() => {
    void load();
  }, [load]);

  const items = inbox?.results ?? [];
  const current = items[selected] ?? null;

  useEffect(() => {
    setPreview(null);
    if (!current || current.kind !== "journal") return;
    let live = true;
    void getJournal(org, current.id).then((r) => {
      if (live && r.status === 200) setPreview(r.body);
    });
    return () => {
      live = false;
    };
  }, [org, current]);

  const act = async (item: ApprovalItem, action: "approve" | "reject", body = {}) => {
    setBusy(true);
    setError(null);
    const reason = (body as { reason?: string }).reason ?? "";
    // Expense claims have their own endpoints (E-04-T11); journals the C-04 workflow's.
    const request =
      item.kind === "expense_claim"
        ? action === "approve"
          ? expenseClaimsApi.approve(org, item.id)
          : expenseClaimsApi.reject(org, item.id, reason)
        : writeApi.action(org, item.id, action, body);
    const result = await request.catch(() => null);
    setBusy(false);
    if (result?.status === 200) {
      setNotice(fm(action === "approve" ? im.approved : im.rejected));
      setRejecting(null);
      setReason("");
      void load();
      return;
    }
    const refusal = result?.body as { detail?: string } | undefined;
    setError(refusal?.detail ?? fm(im.failed));
  };

  const onKey = (event: KeyboardEvent) => {
    if (!items.length || busy || rejecting) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelected((i) => Math.min(items.length - 1, i + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelected((i) => Math.max(0, i - 1));
    } else if ((event.key === "a" || event.key === "A") && current?.can_approve) {
      event.preventDefault();
      void act(current, "approve");
    } else if ((event.key === "r" || event.key === "R") && current?.can_approve) {
      event.preventDefault();
      setRejecting(current);
    }
  };

  if (failed)
    return (
      <ErrorState
        title={fm(im.loadFailed)}
        retryLabel={fm(im.retry)}
        onRetry={() => {
          setFailed(false);
          void load();
        }}
      />
    );

  const money = (amount: string) => formatMoney(amount, { locale });
  const limit = items.find((i) => i.kind === "journal")?.limit;

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold text-fg">{fm(im.title)}</h1>
        {inbox && items.length ? (
          <p className="text-sm font-medium text-fg" data-limit="">
            {limit ? fm(im.yourLimit, { amount: money(limit) }) : fm(im.noLimit)}
          </p>
        ) : null}
      </div>
      {notice ? (
        <p role="status" className="text-sm text-fg-success">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      {inbox && items.length === 0 ? (
        <EmptyState title={fm(im.emptyTitle)} body={fm(im.emptyBody)} />
      ) : null}
      {items.length ? (
        <>
          <p className="text-sm text-fg-muted">
            {fm(im.countsAndKeys, {
              total: inbox?.counts.total ?? 0,
              mine: inbox?.counts.can_approve ?? 0,
            })}
          </p>
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <ul
              role="listbox"
              aria-label={fm(im.list)}
              aria-activedescendant={current ? `${ids}-${current.id}` : undefined}
              tabIndex={0}
              onKeyDown={onKey}
              className="flex flex-col gap-2 rounded-md focus:outline-2 focus:outline-border-focus"
              data-inbox=""
            >
              {items.map((item, index) => (
                <li
                  key={`${item.kind}-${item.id}`}
                  id={`${ids}-${item.id}`}
                  role="option"
                  aria-selected={index === selected}
                  onClick={() => setSelected(index)}
                  className={`flex cursor-pointer flex-col gap-1 rounded-md border p-3 ${
                    index === selected ? "border-border-strong bg-surface-muted" : "border-border"
                  }`}
                  data-item={item.id}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-medium text-fg">{item.title}</span>
                    <span className="tabular-nums font-semibold">{money(item.amount)}</span>
                  </span>
                  <span className="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
                    {item.date ? formatDate(item.date, { locale }) : null}
                    {item.submitted_by
                      ? fm(im.submittedBy, { name: item.submitted_by.name })
                      : null}
                    {item.blocked === "self" ? (
                      <Badge tone="neutral" data-self="">
                        {fm(im.youCreated)}
                      </Badge>
                    ) : null}
                    {item.blocked === "limit" || item.blocked === "no_limit" ? (
                      <Badge tone="warning">{fm(im.overLimit)}</Badge>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
            {current ? (
              <section
                aria-label={fm(im.preview)}
                className="flex flex-col gap-3 rounded-md border border-border p-4"
                data-preview=""
              >
                <h2 className="text-lg font-semibold text-fg">{current.title}</h2>
                <p className="text-sm text-fg-muted">
                  {[current.subtitle, current.date ? formatDate(current.date, { locale }) : ""]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                {preview ? (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-xs text-fg-muted">
                        <th scope="col" className="text-start">
                          {fm(im.account)}
                        </th>
                        <th scope="col" className="text-end">
                          {fm(im.debit)}
                        </th>
                        <th scope="col" className="text-end">
                          {fm(im.credit)}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {preview.lines.map((line) => (
                        <tr key={line.line} className="border-t border-border">
                          <td className="py-1">
                            {fm(im.accountName, {
                              code: line.account.code,
                              name: line.account.name,
                            })}
                          </td>
                          <td className="py-1 text-end tabular-nums">
                            {Number(line.debit) ? money(line.debit) : ""}
                          </td>
                          <td className="py-1 text-end tabular-nums">
                            {Number(line.credit) ? money(line.credit) : ""}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : null}
                <div className="flex flex-wrap items-center gap-3">
                  {current.can_approve ? (
                    <>
                      <Button
                        disabled={busy}
                        aria-keyshortcuts="A"
                        onClick={() => void act(current, "approve")}
                      >
                        {fm(im.approve)}
                      </Button>
                      <Button
                        variant="secondary"
                        disabled={busy}
                        aria-keyshortcuts="R"
                        onClick={() => setRejecting(current)}
                      >
                        {fm(im.reject)}
                      </Button>
                    </>
                  ) : null}
                  <Link href={current.url} className="text-sm font-medium text-fg-link underline">
                    {fm(im.open)}
                  </Link>
                </div>
              </section>
            ) : null}
          </div>
        </>
      ) : null}
      <Dialog
        open={rejecting !== null}
        onOpenChange={(open) => (open ? undefined : setRejecting(null))}
        title={fm(im.rejectTitle)}
        closeLabel={fm(im.close)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setRejecting(null)}>
              {fm(im.cancel)}
            </Button>
            <Button
              disabled={busy || reason.trim().length < MIN_REASON}
              onClick={() => rejecting && void act(rejecting, "reject", { reason: reason.trim() })}
            >
              {fm(im.reject)}
            </Button>
          </>
        }
      >
        <label htmlFor={`${ids}-reason`} className="text-sm font-medium text-fg">
          {fm(im.reason, { min: MIN_REASON })}
        </label>
        <textarea
          id={`${ids}-reason`}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md border border-border bg-surface p-2 text-sm text-fg"
        />
      </Dialog>
    </div>
  );
}
