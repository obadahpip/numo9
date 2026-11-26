"use client";

/**
 * Credit-limit banners inside the invoice editor (D-03a-T16): the customer's credit check for
 * the invoice as it stands (D-03a-T06, `GET …/invoices/<id>/credit`). Informational, never
 * promotional:
 *
 * - **warn** — "Over the credit limit" with the figures; approving still works;
 * - **block** — "Credit limit reached": approval is refused until an override is approved;
 *   **Request override** asks for a reason and notifies the people who approve overrides; a
 *   request already waiting is shown instead of the button;
 * - **override** — an approved override covers the invoice;
 * - within the limit or no limit — nothing.
 *
 * `version` re-checks after the editor saves (the total may have changed).
 */
import { Button, Dialog, formatDate, formatMoney, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { invoiceCreditApi, type InvoiceCredit } from "./api";
import { cm } from "./creditMessages";

const TONE = {
  warn: "border-border bg-surface-warning-subtle",
  block: "border-border-danger bg-surface-danger-subtle",
  override: "border-border bg-surface-info-subtle",
} as const;

export function CreditLimitBanner({
  org,
  id,
  version = 0,
}: Readonly<{ org: string; id: string; version?: number }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [credit, setCredit] = useState<InvoiceCredit | null>(null);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(
    () =>
      invoiceCreditApi
        .check(org, id)
        .then((result) => {
          if (result.status === 200) setCredit(result.body);
        })
        .catch(() => undefined),
    [org, id],
  );
  useEffect(() => {
    void load();
  }, [load, version]);

  if (!credit || !(credit.outcome in TONE)) return null;
  const outcome = credit.outcome as keyof typeof TONE;
  const money = (value: string | null) => (value === null ? "" : formatMoney(value, { locale }));

  const submit = async () => {
    if (!reason.trim()) {
      setReasonError(fm(cm.reasonRequired));
      return;
    }
    setReasonError("");
    setBusy(true);
    setError("");
    const result = await invoiceCreditApi.requestOverride(org, id, reason.trim()).catch(() => null);
    setBusy(false);
    if (result?.status === 201) {
      setCredit(result.body as InvoiceCredit);
      setOpen(false);
      setReason("");
      setNotice(fm(cm.requested));
      return;
    }
    const refusal = result?.body as { detail?: string; reason?: string[] } | undefined;
    setError(fm(cm.failed, { reason: refusal?.detail ?? refusal?.reason?.[0] ?? "" }));
  };

  const title = { warn: cm.warnTitle, block: cm.blockTitle, override: cm.overrideTitle }[outcome];
  const body = { warn: cm.warnBody, block: cm.blockBody, override: cm.overrideBody }[outcome];

  return (
    <section
      aria-labelledby={`${ids}-title`}
      data-credit-banner={outcome}
      className={`flex flex-col gap-2 rounded-md border-2 px-4 py-3 text-sm text-fg ${TONE[outcome]}`}
    >
      <h2 id={`${ids}-title`} className="font-semibold">
        {fm(title)}
      </h2>
      {credit.message ? <p>{credit.message}</p> : null}
      <p>{fm(body)}</p>
      {outcome === "block" && credit.pending_override ? (
        <p data-pending-override="">
          {fm(cm.pending, {
            date: formatDate(credit.pending_override.requested_at.slice(0, 10), { locale }),
          })}
        </p>
      ) : null}
      {outcome === "block" && !credit.pending_override ? (
        <div>
          <Button onClick={() => setOpen(true)}>{fm(cm.request)}</Button>
        </div>
      ) : null}
      <p role="status">{notice}</p>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title={fm(cm.dialogTitle)}
        description={fm(cm.dialogBody, {
          contact: credit.contact.name,
          projected: money(credit.projected),
          over: money(credit.over_by),
          limit: money(credit.limit),
        })}
        closeLabel={fm(cm.cancel)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              {fm(cm.cancel)}
            </Button>
            <Button variant="primary" loading={busy} disabled={busy} onClick={() => void submit()}>
              {fm(cm.send)}
            </Button>
          </>
        }
      >
        <label htmlFor={`${ids}-reason`} className="text-sm font-medium text-fg">
          {fm(cm.reason)}
        </label>
        <textarea
          id={`${ids}-reason`}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          maxLength={500}
          aria-invalid={reasonError ? true : undefined}
          aria-describedby={reasonError ? `${ids}-reason-error` : undefined}
          className="mt-1 w-full rounded-md border border-border bg-surface p-2 text-sm text-fg"
        />
        {reasonError ? (
          <p id={`${ids}-reason-error`} className="text-sm text-fg-danger">
            {reasonError}
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
      </Dialog>
    </section>
  );
}

/**
 * The editor's name for the credit check (D-03a-T13): a warning about this invoice, not a
 * promotional banner — the gap-12 rule (`numo9/no-work-screen-banners`) matches names ending in
 * "Banner".
 */
export { CreditLimitBanner as CreditLimitCheck };
