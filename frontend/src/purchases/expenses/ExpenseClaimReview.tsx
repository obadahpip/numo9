"use client";

/**
 * Expense claim — the approver's view (E-04-T11), `/o/:org/purchases/expense-claims/:id`: the
 * lines (receipts with their tax and the claimable part, trips with the CRA tiers), duplicate
 * receipt warnings (E-04-T07), and Approve / Reject. The buttons are **hidden** whenever the
 * server says the person can't approve (`can_approve` false — their own claim, no permission, or
 * above their limit), with the reason; the server refuses self-approval anyway (E-04-T05).
 */
import {
  Button,
  Dialog,
  StatusBadge,
  formatDate,
  formatMoney,
  type AppLocale,
  type StatusKey,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { expenseClaimsApi, type ExpenseClaim } from "./api";
import { em } from "./messages";

const TZ = "America/Toronto";
const BADGE: Record<ExpenseClaim["status"], StatusKey> = {
  draft: "draft",
  submitted: "awaiting_approval",
  approved: "approved",
  rejected: "failed",
  paid: "paid",
};

export function ExpenseClaimReview({ org, id }: { org: string; id: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [claim, setClaim] = useState<ExpenseClaim | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    const result = await expenseClaimsApi.get(org, id).catch(() => null);
    if (result?.status === 200) setClaim(result.body);
    else setError(result?.body?.detail ?? fm(em.failed));
  }, [org, id, fm]);

  useEffect(() => {
    void load();
  }, [load]);

  const money = (value: string) => formatMoney(value, { locale });
  const day = (value: string) => formatDate(value, { locale, timeZone: TZ });

  const act = async (action: "approve" | "reject") => {
    setBusy(true);
    setError(null);
    const result = await (
      action === "approve"
        ? expenseClaimsApi.approve(org, id)
        : expenseClaimsApi.reject(org, id, reason.trim())
    ).catch(() => null);
    setBusy(false);
    if (result?.status === 200) {
      setClaim(result.body);
      setNotice(fm(action === "approve" ? em.approved : em.rejected));
      setRejecting(false);
      setReason("");
      return;
    }
    setError(result?.body?.detail ?? fm(em.failed));
  };

  if (!claim) {
    return (
      <p role={error ? "alert" : "status"} className="p-4 text-sm text-fg-muted">
        {error ?? fm(em.loading)}
      </p>
    );
  }

  return (
    <article className="flex flex-col gap-4 p-4" aria-labelledby={`${ids}-title`}>
      <header className="flex flex-wrap items-center gap-3">
        <h1 id={`${ids}-title`} className="text-xl font-semibold text-fg">
          {claim.number ? fm(em.title, { number: claim.number }) : fm(em.draftTitle)}
        </h1>
        <StatusBadge status={BADGE[claim.status]} label={claim.status_label} />
      </header>
      <p className="text-sm text-fg">{claim.title}</p>
      <p className="text-sm text-fg-muted">{fm(em.claimant, { name: claim.claimant.name })}</p>
      {claim.submitted_by && claim.submitted_at ? (
        <p className="text-sm text-fg-muted">
          {fm(em.submitted, {
            name: claim.submitted_by.name,
            date: formatDate(new Date(claim.submitted_at), { locale, timeZone: TZ }),
          })}
        </p>
      ) : null}
      {claim.status === "rejected" && claim.decided_by ? (
        <p className="text-sm text-fg" data-rejection="">
          {fm(em.rejectedBecause, { name: claim.decided_by.name, reason: claim.rejection_reason })}
        </p>
      ) : null}
      {claim.warnings.length ? (
        <section
          aria-labelledby={`${ids}-dup`}
          className="rounded-md border border-border bg-surface-warning-subtle p-3 text-sm"
        >
          <h2 id={`${ids}-dup`} className="font-semibold text-fg">
            {fm(em.duplicates)}
          </h2>
          <ul className="mt-1 list-disc pl-5 text-fg">
            {claim.warnings.map((w) => (
              <li key={w.line}>{w.message}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">{fm(em.lines)}</caption>
          <thead>
            <tr className="text-left text-fg-muted">
              <th scope="col" className="p-2">
                {fm(em.colDate)}
              </th>
              <th scope="col" className="p-2">
                {fm(em.colWhat)}
              </th>
              <th scope="col" className="p-2">
                {fm(em.colCategory)}
              </th>
              <th scope="col" className="p-2 text-right">
                {fm(em.colTax)}
              </th>
              <th scope="col" className="p-2 text-right">
                {fm(em.colAmount)}
              </th>
            </tr>
          </thead>
          <tbody>
            {claim.lines.map((line) => (
              <tr key={line.id} className="border-t border-border align-top">
                <td className="p-2 whitespace-nowrap">{day(line.date)}</td>
                <td className="p-2">
                  {line.kind === "mileage" ? (
                    <>
                      <span>
                        {fm(em.trip, {
                          from: line.from_place ?? "",
                          to: line.to_place ?? "",
                          km: line.distance_km ?? "",
                        })}
                      </span>
                      <ul className="text-xs text-fg-muted">
                        {(line.rate_detail ?? []).map((tier) => (
                          <li key={tier.tier}>
                            {fm(em.tiers, { km: tier.km, rate: money(tier.rate) })}
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <>
                      <span>{line.merchant || line.description}</span>
                      <span className="block text-xs text-fg-muted">
                        {line.receipt
                          ? fm(em.receipt, { name: line.receipt.name })
                          : fm(em.noReceipt)}
                      </span>
                    </>
                  )}
                </td>
                <td className="p-2">
                  {line.account
                    ? fm(em.account, { code: line.account.code, name: line.account.name })
                    : null}
                </td>
                <td className="p-2 text-right">
                  {line.split && Number(line.split.tax)
                    ? fm(em.taxCell, {
                        tax: money(line.split.tax),
                        claimable: money(line.split.claimable),
                      })
                    : ""}
                </td>
                <td className="p-2 text-right">{money(line.amount)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-border font-semibold">
              <th scope="row" colSpan={4} className="p-2 text-right">
                {fm(em.total)}
              </th>
              <td className="p-2 text-right">{money(claim.total)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      {notice ? (
        <p role="status" className="text-sm text-fg">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      {claim.can_approve ? (
        <div className="flex flex-wrap gap-3">
          <Button disabled={busy} onClick={() => void act("approve")}>
            {fm(em.approve)}
          </Button>
          <Button variant="secondary" disabled={busy} onClick={() => setRejecting(true)}>
            {fm(em.reject)}
          </Button>
        </div>
      ) : claim.blocked && claim.blocked !== "status" ? (
        <p className="text-sm text-fg-muted" data-blocked={claim.blocked}>
          {fm(em.blocked, { why: claim.blocked })}
        </p>
      ) : null}
      <Dialog
        open={rejecting}
        onOpenChange={(open) => setRejecting(open)}
        title={fm(em.rejectTitle)}
        closeLabel={fm(em.close)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setRejecting(false)}>
              {fm(em.cancel)}
            </Button>
            <Button disabled={busy || !reason.trim()} onClick={() => void act("reject")}>
              {fm(em.reject)}
            </Button>
          </>
        }
      >
        <label htmlFor={`${ids}-reason`} className="text-sm font-medium text-fg">
          {fm(em.reason)}
        </label>
        <textarea
          id={`${ids}-reason`}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-md border border-border bg-surface p-2 text-sm text-fg"
        />
      </Dialog>
    </article>
  );
}
