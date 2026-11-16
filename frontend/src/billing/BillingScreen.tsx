"use client";

import {
  Badge,
  Button,
  Dialog,
  ErrorState,
  formatDate,
  formatMoney,
  LoadingRegion,
  SkeletonTable,
  type BadgeTone,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";
import type { AppLocale } from "@/i18n/locales";

import {
  cancelSubscription,
  getExport,
  getOverview,
  openPortal,
  startCheckout,
  type BillingOverview,
  type ExportState,
  type Interval,
} from "./api";
import { ChangeDialog } from "./ChangeDialog";

export const m = defineMessages({
  title: { id: "billing.title", defaultMessage: "Subscription", description: "Page heading" },
  intro: {
    id: "billing.intro",
    defaultMessage:
      "Your Numo9 package, how you pay and your invoices. Accountants who work in your books are never billed.",
    description: "Text under the heading",
  },
  loading: {
    id: "billing.loading",
    defaultMessage: "Loading the subscription…",
    description: "Screen-reader text while loading",
  },
  loadFailed: {
    id: "billing.loadFailed",
    defaultMessage: "The subscription didn't load",
    description: "Error title",
  },
  loadFailedBody: {
    id: "billing.loadFailedBody",
    defaultMessage: "Verify your connection and try again.",
    description: "Error body",
  },
  ownerOnly: {
    id: "billing.ownerOnly",
    defaultMessage: "Only the organisation's owner can see and change the subscription.",
    description: "Shown to anyone else who opens the page",
  },
  retry: { id: "billing.retry", defaultMessage: "Try again", description: "Button" },
  unavailable: {
    id: "billing.unavailable",
    defaultMessage: "Online payment isn't available right now. Try again later.",
    description: "Billing switched off",
  },
  current: {
    id: "billing.current",
    defaultMessage: "Your package",
    description: "Heading of the current package card",
  },
  noPackage: {
    id: "billing.noPackage",
    defaultMessage: "Trial — every product",
    description: "Current package when the organisation is on its trial",
  },
  status: {
    id: "billing.status",
    defaultMessage:
      "{status, select, trialing {Trial} active {Active} past_due {Payment overdue} read_only {Read-only} cancelled {Cancelled} demo {Demo} other {{status}}}",
    description: "Subscription status badge",
  },
  price: {
    id: "billing.price",
    defaultMessage:
      "{amount, select, none {—} other {{amount}}} {interval, select, year {per year} other {per month}}",
    description: "Price of the current package, e.g. $49.00 per month",
  },
  nextCharge: {
    id: "billing.nextCharge",
    defaultMessage: "Next charge: {amount} on {date}",
    description: "Next renewal",
  },
  endsOn: {
    id: "billing.endsOn",
    defaultMessage: "Cancelled — access until {date}",
    description: "Cancelled at the end of the period",
  },
  pending: {
    id: "billing.pending",
    defaultMessage:
      "Changes to {package} ({interval, select, year {annual} other {monthly}}) on {date}",
    description: "A downgrade scheduled for the end of the period",
  },
  methodLabel: {
    id: "billing.methodLabel",
    defaultMessage: "Payment method:",
    description: "Label before the payment method",
  },
  methodValue: {
    id: "billing.methodValue",
    defaultMessage:
      "{method, select, card {Card} acss_debit {Pre-authorised debit (PAD)} other {Not set up yet}}",
    description: "How the organisation pays",
  },
  updateMethod: {
    id: "billing.updateMethod",
    defaultMessage: "Update payment method",
    description: "Button: opens Stripe's page to change the card or bank account",
  },
  packages: {
    id: "billing.packages",
    defaultMessage: "Packages",
    description: "Heading of the packages offered",
  },
  monthly: { id: "billing.monthly", defaultMessage: "Monthly", description: "Interval toggle" },
  annual: { id: "billing.annual", defaultMessage: "Annual", description: "Interval toggle" },
  intervalLabel: {
    id: "billing.intervalLabel",
    defaultMessage: "Billing interval",
    description: "Accessible name of the monthly/annual toggle",
  },
  perInterval: {
    id: "billing.perInterval",
    defaultMessage: "{amount} {interval, select, year {per year} other {per month}}",
    description: "Price of a package",
  },
  choose: {
    id: "billing.choose",
    defaultMessage: "Choose {package}",
    description: "Button: subscribe to or change to a package",
  },
  yours: {
    id: "billing.yours",
    defaultMessage: "Your package",
    description: "Shown instead of the button on the current package",
  },
  invoices: {
    id: "billing.invoices",
    defaultMessage: "Numo9 invoices",
    description: "Heading of the invoices list",
  },
  noInvoices: {
    id: "billing.noInvoices",
    defaultMessage: "No invoices yet.",
    description: "Empty invoices list",
  },
  colNumber: { id: "billing.colNumber", defaultMessage: "Invoice", description: "Column" },
  colDate: { id: "billing.colDate", defaultMessage: "Date", description: "Column" },
  colTotal: { id: "billing.colTotal", defaultMessage: "Total", description: "Column" },
  colStatus: { id: "billing.colStatus", defaultMessage: "Status", description: "Column" },
  invoiceStatus: {
    id: "billing.invoiceStatus",
    defaultMessage:
      "{status, select, paid {Paid} open {Due} draft {Draft} void {Void} uncollectible {Uncollectible} other {{status}}}",
    description: "Invoice status",
  },
  pdf: {
    id: "billing.pdf",
    defaultMessage: "PDF of invoice {number}",
    description: "Link to download an invoice PDF",
  },
  cancel: {
    id: "billing.cancel",
    defaultMessage: "Cancel subscription",
    description: "Button",
  },
  cancelTitle: {
    id: "billing.cancelTitle",
    defaultMessage: "Cancel the subscription?",
    description: "Dialog title",
  },
  cancelBody: {
    id: "billing.cancelBody",
    defaultMessage:
      "Everyone keeps full access until {date}. After that the organisation is read-only: you can still see and export everything. We'll prepare a full export of your data now.",
    description: "Dialog body",
  },
  cancelConfirm: {
    id: "billing.cancelConfirm",
    defaultMessage: "Cancel at the end of the period",
    description: "Dialog button",
  },
  keep: {
    id: "billing.keep",
    defaultMessage: "Keep the subscription",
    description: "Dialog button / button to undo a cancellation",
  },
  close: { id: "billing.close", defaultMessage: "Close", description: "Dialog close" },
  cancelled: {
    id: "billing.cancelled",
    defaultMessage: "The subscription ends on {date}. Your export is being prepared.",
    description: "Status after cancelling",
  },
  resumed: {
    id: "billing.resumed",
    defaultMessage: "The subscription continues.",
    description: "Status after keeping the subscription",
  },
  failed: {
    id: "billing.failed",
    defaultMessage: "That didn't work. Try again in a moment.",
    description: "Generic action failure",
  },
  export: { id: "billing.export", defaultMessage: "Your data", description: "Heading" },
  exportReady: {
    id: "billing.exportReady",
    defaultMessage: "Download the export (compressed file: CSV, Excel, ledger JSON, documents)",
    description: "Link to the export",
  },
  exportPreparing: {
    id: "billing.exportPreparing",
    defaultMessage: "Your export is being prepared. Come back in a few minutes.",
    description: "Export in progress",
  },
  checkoutDone: {
    id: "billing.checkoutDone",
    defaultMessage: "Thank you. Your payment is being confirmed — this page updates in a moment.",
    description: "Back from Stripe Checkout",
  },
});

const STATUS_TONES: Record<string, BadgeTone> = {
  trialing: "info",
  active: "success",
  past_due: "warning",
  read_only: "danger",
  cancelled: "neutral",
  demo: "neutral",
};

export function money(cents: number | null | undefined, locale: AppLocale): string {
  return formatMoney(((cents ?? 0) / 100).toFixed(2), { locale });
}

type State = "loading" | "failed" | "forbidden" | BillingOverview;

/** Settings → Subscription (U-04-T12): package card, payment method, packages, invoices, cancel. */
export function BillingScreen({ org }: Readonly<{ org: string }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const query = useSearchParams();
  const [state, setState] = useState<State>("loading");
  const [interval, setInterval] = useState<Interval>("month");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [choice, setChoice] = useState<{ code: string; name: string } | null>(null);
  const [exportState, setExportState] = useState<ExportState | null>(null);

  const load = useCallback(async () => {
    const answer = await getOverview(org);
    if (answer.status === 200) {
      setState(answer.body);
      if (answer.body.subscription?.interval) setInterval(answer.body.subscription.interval);
      const latest = await getExport(org);
      if (latest.status === 200 && latest.body.job) setExportState(latest.body);
    } else setState(answer.status === 403 ? "forbidden" : "failed");
  }, [org]);
  useEffect(() => {
    void load();
  }, [load]);

  if (state === "loading")
    return (
      <LoadingRegion label={fm(m.loading)}>
        <SkeletonTable rows={4} columns={4} />
      </LoadingRegion>
    );
  if (state === "forbidden")
    return (
      <section className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">{fm(m.title)}</h1>
        <p className="text-fg-muted">{fm(m.ownerOnly)}</p>
      </section>
    );
  if (state === "failed")
    return (
      <ErrorState
        title={fm(m.loadFailed)}
        body={fm(m.loadFailedBody)}
        retryLabel={fm(m.retry)}
        onRetry={() => void load()}
      />
    );

  const sub = state.subscription;
  const date = (iso: string | null | undefined) =>
    iso ? formatDate(new Date(iso), { locale }) : "";
  const paying = Boolean(sub?.paying);

  const choose = async (pkg: { code: string; name: string }) => {
    if (!paying) {
      setBusy(true);
      const answer = await startCheckout(org, { package: pkg.code, interval });
      setBusy(false);
      if (answer.status === 201) window.location.assign(answer.body.url);
      else setStatus(fm(m.failed));
      return;
    }
    setChoice(pkg);
  };

  const portal = async () => {
    setBusy(true);
    const answer = await openPortal(org);
    setBusy(false);
    if (answer.status === 201) window.location.assign(answer.body.url);
    else setStatus(fm(m.failed));
  };

  const cancel = async (resume: boolean) => {
    setBusy(true);
    const answer = await cancelSubscription(org, resume);
    setBusy(false);
    setCancelOpen(false);
    if (answer.status !== 200) {
      setStatus(fm(m.failed));
      return;
    }
    if (answer.body.export) setExportState(answer.body.export);
    setStatus(
      resume ? fm(m.resumed) : fm(m.cancelled, { date: date(sub?.current_period_end ?? null) }),
    );
    await load();
  };

  return (
    <div className="flex flex-col gap-8">
      <header className="flex max-w-3xl flex-col gap-2">
        <h1 className="text-2xl font-semibold">{fm(m.title)}</h1>
        <p className="text-fg-muted">{fm(m.intro)}</p>
      </header>
      <p role="status" aria-live="polite" className="text-fg-muted" data-billing-status>
        {query.get("checkout") === "success" && !status ? fm(m.checkoutDone) : status}
      </p>
      {!state.billing_available ? <p className="text-fg-muted">{fm(m.unavailable)}</p> : null}

      <section
        aria-labelledby="billing-current"
        className="flex max-w-3xl flex-col gap-3 rounded-lg border border-border p-5"
        data-current-package
      >
        <div className="flex flex-wrap items-center gap-3">
          <h2 id="billing-current" className="text-lg font-semibold">
            {fm(m.current)}
          </h2>
          {sub ? (
            <Badge tone={STATUS_TONES[sub.status] ?? "neutral"} dot>
              {fm(m.status, { status: sub.status })}
            </Badge>
          ) : null}
        </div>
        <p className="text-xl font-semibold">{sub?.package?.name ?? fm(m.noPackage)}</p>
        {sub?.package ? (
          <p>
            {fm(m.price, {
              amount: sub.amount_cents == null ? "none" : money(sub.amount_cents, locale),
              interval: sub.interval,
            })}
          </p>
        ) : null}
        {sub?.paying && sub.current_period_end && !sub.cancel_at_period_end ? (
          <p data-next-charge>
            {fm(m.nextCharge, {
              amount: money(sub.amount_cents, locale),
              date: date(sub.current_period_end),
            })}
          </p>
        ) : null}
        {sub?.cancel_at_period_end ? (
          <p data-ends>{fm(m.endsOn, { date: date(sub.current_period_end) })}</p>
        ) : null}
        {state.pending_change ? (
          <p data-pending>
            {fm(m.pending, {
              package: state.pending_change.package.name,
              interval: state.pending_change.interval,
              date: date(state.pending_change.effective_at),
            })}
          </p>
        ) : null}
        <div className="flex flex-wrap items-center gap-3 border-t border-border pt-3">
          <span className="text-fg-muted">{fm(m.methodLabel)}</span>
          <span data-method>
            {fm(m.methodValue, { method: sub?.payment_method_type || "none" })}
          </span>
          {paying ? (
            <Button variant="secondary" disabled={busy} onClick={() => void portal()}>
              {fm(m.updateMethod)}
            </Button>
          ) : null}
        </div>
        {paying ? (
          <div className="flex gap-3 border-t border-border pt-3">
            {sub?.cancel_at_period_end ? (
              <Button variant="secondary" disabled={busy} onClick={() => void cancel(true)}>
                {fm(m.keep)}
              </Button>
            ) : (
              <Button variant="danger" disabled={busy} onClick={() => setCancelOpen(true)}>
                {fm(m.cancel)}
              </Button>
            )}
          </div>
        ) : null}
      </section>

      <section aria-labelledby="billing-packages" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-4">
          <h2 id="billing-packages" className="text-lg font-semibold">
            {fm(m.packages)}
          </h2>
          <div role="group" aria-label={fm(m.intervalLabel)} className="flex gap-1">
            {(["month", "year"] as const).map((value) => (
              <Button
                key={value}
                variant={interval === value ? "primary" : "secondary"}
                aria-pressed={interval === value}
                onClick={() => setInterval(value)}
              >
                {value === "month" ? fm(m.monthly) : fm(m.annual)}
              </Button>
            ))}
          </div>
        </div>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {state.packages.map((pkg) => {
            const cents = pkg.prices[interval];
            const isCurrent =
              sub?.package?.code === pkg.code && sub.interval === interval && paying;
            return (
              <li
                key={pkg.code}
                className="flex flex-col gap-2 rounded-lg border border-border p-4"
                data-package={pkg.code}
              >
                <h3 className="font-semibold">{pkg.name}</h3>
                <p>
                  {cents == null
                    ? ""
                    : fm(m.perInterval, { amount: money(cents, locale), interval })}
                </p>
                {isCurrent ? (
                  <p className="text-fg-muted">{fm(m.yours)}</p>
                ) : (
                  <Button
                    disabled={busy || cents == null || !state.billing_available}
                    onClick={() => void choose(pkg)}
                  >
                    {fm(m.choose, { package: pkg.name })}
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <section aria-labelledby="billing-invoices" className="flex max-w-3xl flex-col gap-3">
        <h2 id="billing-invoices" className="text-lg font-semibold">
          {fm(m.invoices)}
        </h2>
        {state.invoices.length === 0 ? (
          <p className="text-fg-muted">{fm(m.noInvoices)}</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-fg-muted">
                <th scope="col" className="py-2 text-start">
                  {fm(m.colNumber)}
                </th>
                <th scope="col" className="py-2 text-start">
                  {fm(m.colDate)}
                </th>
                <th scope="col" className="py-2 text-end">
                  {fm(m.colTotal)}
                </th>
                <th scope="col" className="py-2 ps-4 text-start">
                  {fm(m.colStatus)}
                </th>
              </tr>
            </thead>
            <tbody>
              {state.invoices.map((invoice) => (
                <tr
                  key={invoice.id}
                  className="border-b border-border"
                  data-invoice={invoice.number}
                >
                  <td className="py-2">
                    {invoice.pdf_url ? (
                      <a
                        href={invoice.pdf_url}
                        className="text-fg-accent underline"
                        aria-label={fm(m.pdf, { number: invoice.number })}
                      >
                        {invoice.number}
                      </a>
                    ) : (
                      invoice.number
                    )}
                  </td>
                  <td className="py-2">{date(invoice.issued_at)}</td>
                  <td className="py-2 text-end tabular-nums">
                    {money(invoice.total_cents, locale)}
                  </td>
                  <td className="py-2 ps-4">{fm(m.invoiceStatus, { status: invoice.status })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {exportState?.job ? (
        <section aria-labelledby="billing-export" className="flex max-w-3xl flex-col gap-2">
          <h2 id="billing-export" className="text-lg font-semibold">
            {fm(m.export)}
          </h2>
          {exportState.url ? (
            <a href={exportState.url} className="text-fg-accent underline" data-export-link>
              {fm(m.exportReady)}
            </a>
          ) : (
            <p className="text-fg-muted">{fm(m.exportPreparing)}</p>
          )}
        </section>
      ) : null}

      <Dialog
        open={cancelOpen}
        onOpenChange={setCancelOpen}
        title={fm(m.cancelTitle)}
        closeLabel={fm(m.close)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCancelOpen(false)}>
              {fm(m.keep)}
            </Button>
            <Button variant="danger" disabled={busy} onClick={() => void cancel(false)}>
              {fm(m.cancelConfirm)}
            </Button>
          </>
        }
      >
        <p>{fm(m.cancelBody, { date: date(sub?.current_period_end ?? null) })}</p>
      </Dialog>

      {choice ? (
        <ChangeDialog
          org={org}
          target={choice}
          interval={interval}
          current={sub}
          onClose={() => setChoice(null)}
          onDone={(message) => {
            setChoice(null);
            setStatus(message);
            void load();
          }}
        />
      ) : null}
    </div>
  );
}
