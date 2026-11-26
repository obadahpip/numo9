"use client";

/**
 * Invoice editor (D-03a-T13), `/o/:org/sales/invoices/new` and `/o/:org/sales/invoices/:id`: the
 * header (customer, invoice date, due date from the customer's terms when left empty, reference,
 * tax mode), the shared document grid (D-01, sales side: revenue accounts and sales tax codes;
 * the first line starts on the first revenue account, so a first invoice is a customer, a line and
 * Approve), the live totals with the tax per component, notes, and the attachments. A posted
 * invoice opens read-only. The action bar, the posting preview and the period ribbon come in
 * through `actions` / `ribbon` (D-03a-T14).
 */
import {
  Badge,
  Button,
  DocumentLines,
  DocumentTotals,
  ErrorState,
  Input,
  Skeleton,
  formatMoney,
  newDocumentLine,
  parseLineDiscount,
  type AppLocale,
  type DocumentGridLine,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useState, type ReactNode } from "react";

import { accountsApi, type Account } from "@/accounts/api";
import { pickerAccount } from "@/accounts/picker";
import { pickerTaxCode } from "@/banking/MoneyForm";
import { contactsApi, type ContactSummary } from "@/contacts/api";
import { DocumentWarnings } from "@/documents/DocumentWarnings";
import { useDocumentLinesLabels, useDocumentTotalsLabels } from "@/documents/labels";
import { TaxNotices } from "@/documents/TaxNotices";
import { useDocumentCalculation, type MirrorTaxCode } from "@/documents/useDocumentCalculation";
import { useTaxDefaults } from "@/documents/useTaxDefaults";
import { filesApi } from "@/files/api";
import { uploadFile } from "@/files/upload";
import { useFormatMessage } from "@/i18n";
import { taxApi, type TaxCode } from "@/tax/api";

import {
  invoiceUrl,
  invoicesApi,
  type Invoice,
  type InvoiceInput,
  type InvoiceLine,
  type Refusal,
  type TaxMode,
} from "./api";
import { im, statusLabels } from "./messages";

const today = () => new Date().toISOString().slice(0, 10);

export function gridLine(line: InvoiceLine): DocumentGridLine {
  const value = Number(line.discount_value);
  return {
    ...newDocumentLine(),
    id: line.id,
    description: line.description,
    quantity: String(Number(line.quantity)),
    unitPrice: String(Number(line.unit_price).toFixed(2)),
    discount:
      line.discount_type === "percent"
        ? `${value}%`
        : line.discount_type === "amount"
          ? value.toFixed(2)
          : "",
    account: line.account?.id ?? null,
    taxCode: line.tax_code?.id ?? null,
  };
}

/** The lines the server receives: every line with something on it. */
export function invoiceLines(
  lines: readonly DocumentGridLine[],
  overridden: (id: string) => boolean = () => false,
) {
  return lines
    .filter((line) => line.description || Number(line.unitPrice) > 0)
    .map((line) => {
      const discount = parseLineDiscount(line.discount) ?? { type: "none" as const, value: "0" };
      return {
        description: line.description,
        quantity: line.quantity || "1",
        unit_price: line.unitPrice || "0",
        discount_type: discount.type,
        discount_value: discount.value,
        account: line.account,
        tax_code: line.taxCode,
        tax_overridden: overridden(line.id),
      };
    });
}

function mirrorTaxCode(code: TaxCode): MirrorTaxCode {
  return {
    id: code.id,
    components: code.components.map((c) => ({ key: c.key, name: c.name, rate: c.rate })),
  };
}

/** What the action bar works with (D-03a-T14). */
export interface InvoiceActionContext {
  invoice: Invoice | null;
  busy: boolean;
  /** Save the form (create or update); the saved invoice, or null when refused. A new invoice
   * moves to its own URL unless `stay` (then `open` it once the action is done). */
  save: (stay?: boolean) => Promise<Invoice | null>;
  /** Move a new invoice to its own URL. */
  open: (invoice: Invoice) => void;
  /** Show the invoice the server answered. */
  show: (invoice: Invoice, notice?: string) => void;
  refuse: (refusal: Refusal) => void;
  setBusy: (busy: boolean) => void;
  ready: boolean;
}

export interface InvoiceEditorProps {
  org: string;
  /** An existing invoice; empty for a new one. */
  id?: string;
  navigate?: (href: string) => void;
  /** The action bar (D-03a-T14); without it, Save draft. */
  actions?: (context: InvoiceActionContext) => ReactNode;
  /** The period ribbon above the form (D-03a-T14), for the invoice and the date shown. */
  ribbon?: (invoice: Invoice | null, date: string, refresh: number) => ReactNode;
  /** Banners under the totals (credit limit, D-03a-T16). */
  banners?: (invoice: Invoice | null, refresh: number) => ReactNode;
}

export function InvoiceEditor({
  org,
  id,
  navigate,
  actions,
  ribbon,
  banners,
}: Readonly<InvoiceEditorProps>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const linesLabels = useDocumentLinesLabels("sales");
  const totalsLabels = useDocumentTotalsLabels();

  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(Boolean(id));
  const [customers, setCustomers] = useState<ContactSummary[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [codes, setCodes] = useState<TaxCode[]>([]);

  const [customer, setCustomer] = useState("");
  const [date, setDate] = useState(today);
  const [dueDate, setDueDate] = useState("");
  const [reference, setReference] = useState("");
  const [taxMode, setTaxMode] = useState<TaxMode>("exclusive");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DocumentGridLine[]>(() => [newDocumentLine()]);
  const [files, setFiles] = useState<{ id: string; name: string }[]>([]);
  const [upload, setUpload] = useState<{ name: string; failed: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [refresh, setRefresh] = useState(0);

  const fill = useCallback((loaded: Invoice) => {
    setInvoice(loaded);
    setCustomer(loaded.customer.id);
    setDate(loaded.date);
    setDueDate(loaded.due_date ?? "");
    setReference(loaded.reference);
    setTaxMode(loaded.tax_mode);
    setNotes(loaded.notes);
    setFiles(loaded.attachments);
    setLines(loaded.lines.length ? loaded.lines.map(gridLine) : [newDocumentLine()]);
  }, []);

  useEffect(() => {
    void accountsApi
      .list(org, "active")
      .then((r) => setAccounts(r.status === 200 ? r.body.results : []));
    void contactsApi
      .list(org, { status: "active", role: "customer" })
      .then((r) => setCustomers(r.status === 200 ? r.body.results : []));
  }, [org]);

  useEffect(() => {
    void taxApi
      .codes(org, { side: "sales", date })
      .then((r) => setCodes(r.status === 200 ? r.body.results : []))
      .catch(() => setCodes([]));
  }, [org, date]);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    void invoicesApi.get(org, id).then((result) => {
      setLoading(false);
      if (result.status === 200 && result.body.id) fill(result.body);
      else setFailed(true);
    });
  }, [org, id, fill]);

  // A new invoice's first line starts on the first revenue account (fewest clicks, T13).
  const revenue = useMemo(() => accounts.filter((a) => a.type === "revenue"), [accounts]);
  useEffect(() => {
    if (id || !revenue[0]) return;
    const first = revenue[0].id;
    setLines((current) => {
      const [only] = current;
      return current.length === 1 && only && !only.account
        ? [{ ...only, account: first }]
        : current;
    });
  }, [id, revenue]);

  const pickerAccounts = useMemo(() => accounts.map(pickerAccount), [accounts]);
  const pickerCodes = useMemo(() => codes.map(pickerTaxCode), [codes]);
  const accountDefaults = useMemo(
    () =>
      Object.fromEntries(
        accounts.filter((a) => a.default_tax_key).map((a) => [a.id, a.default_tax_key]),
      ),
    [accounts],
  );
  const calculation = useDocumentCalculation({
    org,
    side: "sales",
    kind: "invoice",
    date,
    taxMode,
    discountType: "none",
    discountValue: "0",
    lines,
    taxCodes: useMemo(() => codes.map(mirrorTaxCode), [codes]),
    contact: customer || null,
  });

  const editable = !invoice || invoice.status === "draft";
  const taxDefaults = useTaxDefaults({
    org,
    side: "sales",
    date,
    contact: customer || null,
    lines,
    setLines,
    enabled: editable,
  });

  const attach = async (picked: FileList | null) => {
    const file = picked?.[0];
    if (!file) return;
    setUpload({ name: file.name, failed: false });
    const state = await uploadFile(org, file, () => undefined);
    if (state.kind !== "done") return setUpload({ name: file.name, failed: true });
    setUpload(null);
    setFiles((current) => [...current, { id: state.document.id, name: state.document.name }]);
    if (invoice) await filesApi.attach(org, state.document.id, "sales.Invoice", invoice.id);
  };

  const body = (): InvoiceInput => ({
    customer,
    date,
    due_date: dueDate || null,
    reference,
    tax_mode: taxMode,
    notes,
    lines: invoiceLines(lines, (line) => Boolean(taxDefaults.taxOverridden?.[line])),
    ...(invoice ? { version: invoice.version } : { attachments: files.map((f) => f.id) }),
  });

  const show = (loaded: Invoice, message = "") => {
    fill(loaded);
    setRefusal(null);
    setNotice(message);
    setRefresh((n) => n + 1);
  };

  const open = (saved: Invoice) => {
    const href = invoiceUrl(org, saved.id);
    if (navigate) navigate(href);
    else window.history.replaceState(null, "", href);
  };

  const save = async (stay = false): Promise<Invoice | null> => {
    setRefusal(null);
    const result = invoice
      ? await invoicesApi.update(org, invoice.id, body())
      : await invoicesApi.create(org, body());
    if (result.status === 200 || result.status === 201) {
      fill(result.body);
      setRefresh((n) => n + 1);
      if (!invoice && !stay) open(result.body);
      return result.body;
    }
    setRefusal(result.body && typeof result.body === "object" ? result.body : {});
    return null;
  };

  const saveDraft = async () => {
    if (busy || !customer) return;
    setBusy(true);
    setNotice("");
    const saved = await save();
    if (saved) setNotice(fm(im.saved));
    setBusy(false);
  };

  if (failed) {
    return (
      <ErrorState
        title={fm(im.loadFailed)}
        retryLabel={fm(im.retry)}
        onRetry={() => window.location.reload()}
      />
    );
  }
  if (loading) return <Skeleton className="h-96" />;

  const field = "flex flex-col gap-1 text-sm font-medium text-fg";
  const select =
    "min-h-touch-target rounded-md border border-border bg-surface px-2 text-sm text-fg";
  const refusalText = refusal?.detail ?? (refusal ? fm(im.failed) : "");
  const context: InvoiceActionContext = {
    invoice,
    busy,
    save,
    open,
    show,
    refuse: (r) => {
      setNotice("");
      setRefusal(r);
    },
    setBusy,
    ready: Boolean(customer),
  };

  return (
    <form
      aria-labelledby={`${ids}-title`}
      onSubmit={(event) => {
        event.preventDefault();
        void saveDraft();
      }}
      className="flex min-w-0 max-w-6xl flex-col gap-5"
      data-invoice-editor=""
      noValidate
    >
      <div className="flex flex-wrap items-center gap-3">
        <h1 id={`${ids}-title`} className="text-2xl font-semibold text-fg">
          {invoice?.number
            ? fm(im.title, { number: invoice.number })
            : invoice
              ? fm(im.draftTitle)
              : fm(im.newTitle)}
        </h1>
        {invoice ? <Badge tone="neutral">{fm(statusLabels[invoice.status])}</Badge> : null}
        {invoice && invoice.status !== "draft" ? (
          <span className="text-sm text-fg-muted">
            {fm(im.amountDue, { amount: formatMoney(invoice.amount_due, { locale }) })}
          </span>
        ) : null}
      </div>
      {ribbon ? ribbon(invoice, date, refresh) : null}
      {!editable && invoice ? (
        <p className="rounded-md bg-surface-info-subtle p-3 text-sm text-fg" role="note">
          {fm(im.readOnly, { status: fm(statusLabels[invoice.status]).toLowerCase() })}
        </p>
      ) : null}
      <fieldset
        disabled={!editable}
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
        aria-label={fm(im.form)}
      >
        <label className={field}>
          {fm(im.customer)}
          <select
            value={customer}
            onChange={(e) => setCustomer(e.target.value)}
            required
            className={select}
          >
            <option value="">{fm(im.chooseCustomer)}</option>
            {customers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.display_name}
              </option>
            ))}
          </select>
        </label>
        <label className={field}>
          {fm(im.date)}
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
        <label className={field}>
          {fm(im.dueDate)}
          <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          <span className="text-xs font-normal text-fg-muted">{fm(im.dueDateHint)}</span>
        </label>
        <label className={field}>
          {fm(im.reference)}
          <Input value={reference} onChange={(e) => setReference(e.target.value)} />
        </label>
        <label className={field}>
          {fm(im.taxMode)}
          <select
            value={taxMode}
            onChange={(e) => setTaxMode(e.target.value as TaxMode)}
            className={select}
          >
            <option value="exclusive">{fm(im.taxExclusive)}</option>
            <option value="inclusive">{fm(im.taxInclusive)}</option>
            <option value="no_tax">{fm(im.taxNone)}</option>
          </select>
        </label>
      </fieldset>

      <DocumentLines
        lines={lines}
        onChange={setLines}
        side="sales"
        date={date}
        accounts={pickerAccounts}
        taxCodes={pickerCodes}
        amounts={calculation.amounts}
        accountDefaults={accountDefaults}
        taxWhy={taxDefaults.taxWhy}
        taxAuto={taxDefaults.taxAuto}
        taxOverridden={taxDefaults.taxOverridden}
        onResetTax={taxDefaults.reset}
        labels={linesLabels}
        locale={locale}
        readOnly={!editable}
      />

      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="flex flex-1 flex-col gap-4">
          <label className={field}>
            {fm(im.notes)}
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              disabled={!editable}
              className="rounded-md border border-border bg-surface p-2 text-sm font-normal text-fg"
            />
          </label>
          <section aria-labelledby={`${ids}-files`} className="flex flex-col gap-2">
            <div className="flex items-center gap-3">
              <h2 id={`${ids}-files`} className="text-sm font-semibold text-fg">
                {fm(im.attachments)}
              </h2>
              <label className="cursor-pointer rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-fg">
                {fm(im.attach)}
                <input
                  type="file"
                  className="sr-only"
                  onChange={(e) => void attach(e.target.files)}
                />
              </label>
            </div>
            {upload ? (
              <p role="status" className="text-sm text-fg-muted">
                {upload.failed
                  ? fm(im.uploadFailed, { name: upload.name })
                  : fm(im.uploading, { name: upload.name })}
              </p>
            ) : null}
            {files.length ? (
              <ul className="text-sm" data-invoice-attachments="">
                {files.map((file) => (
                  <li key={file.id}>{file.name}</li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-fg-muted">{fm(im.noAttachments)}</p>
            )}
          </section>
        </div>
        <div className="flex flex-col gap-2 xl:w-96">
          <DocumentWarnings warnings={calculation.warnings} />
          <TaxNotices notices={taxDefaults.notices} />
          <DocumentTotals
            value={calculation.totals}
            discountType="none"
            discountValue="0"
            noDiscount
            readOnly
            pending={calculation.pending}
            labels={totalsLabels}
            locale={locale}
          />
          {banners ? banners(invoice, refresh) : null}
        </div>
      </div>

      {refusal ? (
        <p
          role="alert"
          className="rounded-md border border-border-danger p-3 text-sm font-semibold text-fg-danger"
          data-refusal={refusal.code ?? ""}
        >
          {refusalText}
        </p>
      ) : null}
      <p role="status" className="text-sm text-fg">
        {notice}
      </p>
      {actions ? (
        actions(context)
      ) : editable ? (
        <div className="flex flex-wrap gap-3">
          <Button type="submit" variant="primary" disabled={busy || !customer}>
            {busy ? fm(im.saving) : fm(im.saveDraft)}
          </Button>
        </div>
      ) : null}
    </form>
  );
}
