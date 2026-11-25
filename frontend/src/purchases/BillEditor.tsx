"use client";

/**
 * Bill editor (E-02-T11): a **split view** — the supplier's invoice on the left (the attached
 * PDF or image, from the documents inbox "Create a bill" or dropped here), the bill form on the
 * right — so a bill is keyed from its document without leaving the page. The form: supplier,
 * supplier invoice number, dates (the due date from the supplier's terms when left empty),
 * reference, department, tax mode, holdback, notes, the shared document grid (D-01, purchase
 * side: expense/asset accounts and purchase tax codes only) and the totals; Save draft, Submit
 * for approval, Approve. A posted bill opens read-only.
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
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import { accountsApi, type Account } from "@/accounts/api";
import { pickerAccount } from "@/accounts/picker";
import { apiRequest } from "@/auth/client";
import { pickerTaxCode } from "@/banking/MoneyForm";
import { contactsApi, type ContactSummary } from "@/contacts/api";
import { useDocumentLinesLabels, useDocumentTotalsLabels } from "@/documents/labels";
import { DocumentWarnings } from "@/documents/DocumentWarnings";
import { useDocumentCalculation, type MirrorTaxCode } from "@/documents/useDocumentCalculation";
import { filesApi, type FileDocument } from "@/files/api";
import { uploadFile } from "@/files/upload";
import { useFormatMessage } from "@/i18n";
import { taxApi, type TaxCode } from "@/tax/api";

import {
  billsApi,
  type Bill,
  type BillInput,
  type BillLine,
  type HoldbackType,
  type Refusal,
  type TaxMode,
} from "./api";
import { match as matchMessages, m, routing as routingMessages, statusLabels } from "./messages";

const today = () => new Date().toISOString().slice(0, 10);

export function billUrl(org: string, id: string): string {
  return `/o/${org}/purchases/bills/${id}`;
}

export function gridLine(line: BillLine): DocumentGridLine {
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
export function billLines(lines: readonly DocumentGridLine[], poLines: Record<string, string>) {
  return lines
    .filter((line) => line.account || line.description || Number(line.unitPrice) > 0)
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
        po_line: poLines[line.id] ?? null,
      };
    });
}

function mirrorTaxCode(code: TaxCode): MirrorTaxCode {
  return {
    id: code.id,
    components: code.components.map((c) => ({
      key: c.key,
      name: c.name,
      rate: c.rate,
      ...(c.recoverable_pct === null ? {} : { claimable_pct: c.recoverable_pct }),
    })),
  };
}

interface DocumentPaneProps {
  org: string;
  document: FileDocument | null;
  onAttach: (files: FileList | null) => void;
  upload: { name: string; failed: boolean } | null;
}

function DocumentPane({ org, document, onAttach, upload }: DocumentPaneProps) {
  const fm = useFormatMessage();
  const ids = useId();
  const [url, setUrl] = useState<string | null>(null);

  // The file is fetched from its signed URL (connect-src allows the files bucket) and shown
  // from a blob: URL — the only frame source the CSP allows (frame-src blob:, D-03a-T15).
  useEffect(() => {
    setUrl(null);
    if (!document) return;
    let cancelled = false;
    let made = "";
    const variant =
      document.mime.startsWith("image/") && document.preview_status === "ready"
        ? "preview"
        : "file";
    void filesApi.signedUrl(org, document.id, variant).then(async (result) => {
      if (cancelled || result.status !== 200 || typeof result.body.url !== "string") return;
      try {
        const response = await fetch(result.body.url);
        if (!response.ok) return;
        const blob = await response.blob();
        if (cancelled) return;
        made = URL.createObjectURL(blob);
        setUrl(made);
      } catch {
        /* the pane keeps its placeholder; the form still works */
      }
    });
    return () => {
      cancelled = true;
      if (made) URL.revokeObjectURL(made);
    };
  }, [org, document]);

  const image = document?.mime.startsWith("image/");
  return (
    <section
      aria-labelledby={`${ids}-title`}
      className="flex min-h-[28rem] flex-col gap-2 rounded-lg border border-border bg-surface-subtle p-3 lg:sticky lg:top-4 lg:h-[calc(100vh-8rem)]"
      data-bill-document=""
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        onAttach(event.dataTransfer.files);
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <h2 id={`${ids}-title`} className="text-sm font-semibold text-fg">
          {fm(m.document)}
        </h2>
        <label className="cursor-pointer rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-fg">
          {fm(m.attach)}
          <input type="file" className="sr-only" onChange={(e) => onAttach(e.target.files)} />
        </label>
      </div>
      {upload ? (
        <p role="status" className="text-sm text-fg-muted">
          {upload.failed
            ? fm(m.uploadFailed, { name: upload.name })
            : fm(m.uploading, { name: upload.name })}
        </p>
      ) : null}
      {!document ? (
        <div className="flex flex-1 items-center justify-center rounded-md border-2 border-dashed border-border p-6 text-center text-sm text-fg-muted">
          {fm(m.noDocument)}
        </div>
      ) : url ? (
        // PDFs and images alike: the browser shows both in a frame (no <img> optimisation for
        // a signed, short-lived URL).
        <iframe
          src={url}
          title={fm(m.documentFrame, { name: document.name })}
          className="w-full flex-1 rounded-md border border-border bg-surface"
          data-image={image ? "" : undefined}
        />
      ) : (
        <Skeleton className="flex-1" />
      )}
      {document && url ? (
        <a href={url} target="_blank" rel="noreferrer" className="text-sm text-fg underline">
          {fm(m.openFile)}
        </a>
      ) : null}
    </section>
  );
}

export interface BillEditorProps {
  org: string;
  /** An existing bill; empty for a new one. */
  id?: string;
  /** A document of the inbox to bill from (`?document=`). */
  documentId?: string | null;
  navigate?: (href: string) => void;
  /** Panels under the form (duplicate warnings, match panel, routing, E-02-T12…T14). */
  panels?: (bill: Bill | null, refresh: number) => ReactNode;
  /** The supplier invoice number field (the live check replaces it, E-02-T12). */
  renderNumber?: (args: {
    supplier: string;
    value: string;
    onChange: (value: string) => void;
    exclude?: string;
    id: string;
  }) => ReactNode;
}

export function BillEditor({
  org,
  id,
  documentId,
  navigate,
  panels,
  renderNumber,
}: Readonly<BillEditorProps>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const linesLabels = useDocumentLinesLabels("purchase");
  const totalsLabels = useDocumentTotalsLabels();

  const [bill, setBill] = useState<Bill | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(Boolean(id));
  const [suppliers, setSuppliers] = useState<ContactSummary[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [codes, setCodes] = useState<TaxCode[]>([]);
  const [document, setDocument] = useState<FileDocument | null>(null);
  const [upload, setUpload] = useState<{ name: string; failed: boolean } | null>(null);

  const [supplier, setSupplier] = useState("");
  const [number, setNumber] = useState("");
  const [date, setDate] = useState(today);
  const [dueDate, setDueDate] = useState("");
  const [reference, setReference] = useState("");
  const [department, setDepartment] = useState("");
  const [taxMode, setTaxMode] = useState<TaxMode>("exclusive");
  const [holdbackType, setHoldbackType] = useState<HoldbackType>("none");
  const [holdbackValue, setHoldbackValue] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DocumentGridLine[]>(() => [newDocumentLine()]);
  const [poLines, setPoLines] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [refresh, setRefresh] = useState(0);

  const fill = useCallback((loaded: Bill) => {
    setBill(loaded);
    setSupplier(loaded.supplier.id);
    setNumber(loaded.supplier_invoice_no);
    setDate(loaded.date);
    setDueDate(loaded.due_date ?? "");
    setReference(loaded.reference);
    setDepartment(loaded.department);
    setTaxMode(loaded.tax_mode);
    setHoldbackType(loaded.holdback_type);
    setHoldbackValue(loaded.holdback_type === "none" ? "" : String(Number(loaded.holdback_value)));
    setNotes(loaded.notes);
    setLines(loaded.lines.length ? loaded.lines.map(gridLine) : [newDocumentLine()]);
    setPoLines(
      Object.fromEntries(
        loaded.lines.filter((l) => l.po_line).map((l) => [l.id, l.po_line as string]),
      ),
    );
  }, []);

  useEffect(() => {
    void accountsApi
      .list(org, "active")
      .then((r) => setAccounts(r.status === 200 ? r.body.results : []));
    void contactsApi
      .list(org, { status: "active", role: "supplier" })
      .then((r) => setSuppliers(r.status === 200 ? r.body.results : []));
  }, [org]);

  useEffect(() => {
    void taxApi
      .codes(org, { side: "purchase", date })
      .then((r) => setCodes(r.status === 200 ? r.body.results : []))
      .catch(() => setCodes([]));
  }, [org, date]);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    void billsApi.get(org, id).then((result) => {
      setLoading(false);
      if (result.status === 200 && result.body.id) fill(result.body);
      else setFailed(true);
    });
    void filesApi.attachments(org, "purchases.Bill", id).then((result) => {
      const first = result.status === 200 ? result.body.results[0] : undefined;
      if (first) setDocument(first.document);
    });
  }, [org, id, fill]);

  useEffect(() => {
    if (id || !documentId) return;
    void apiRequest<FileDocument>(`/api/v1/o/${encodeURIComponent(org)}/files/${documentId}`).then(
      (result) => {
        if (result.status === 200 && result.body.id) setDocument(result.body);
      },
    );
  }, [org, id, documentId]);

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
    side: "purchases",
    kind: "bill",
    date,
    taxMode,
    discountType: "none",
    discountValue: "0",
    lines,
    taxCodes: useMemo(() => codes.map(mirrorTaxCode), [codes]),
    contact: supplier || null,
  });

  const editable = !bill || bill.status === "draft";
  const attach = async (files: FileList | null) => {
    const file = files?.[0];
    if (!file) return;
    setUpload({ name: file.name, failed: false });
    const state = await uploadFile(org, file, () => undefined);
    if (state.kind === "done") {
      setDocument(state.document);
      setUpload(null);
      if (bill) await filesApi.attach(org, state.document.id, "purchases.Bill", bill.id);
    } else setUpload({ name: file.name, failed: true });
  };

  const body = (): BillInput => ({
    supplier,
    date,
    due_date: dueDate || null,
    supplier_invoice_no: number,
    reference,
    tax_mode: taxMode,
    department,
    notes,
    holdback_type: holdbackType,
    holdback_value: holdbackType === "none" ? "0" : holdbackValue || "0",
    lines: billLines(lines, poLines),
    ...(bill ? { version: bill.version } : { document: document?.id ?? null }),
  });

  const save = async (): Promise<Bill | null> => {
    const result = bill
      ? await billsApi.update(org, bill.id, body())
      : await billsApi.create(org, body());
    if (result.status === 200 || result.status === 201) {
      fill(result.body);
      if (!bill) {
        const href = billUrl(org, result.body.id);
        if (navigate) navigate(href);
        else window.history.replaceState(null, "", href);
      }
      return result.body;
    }
    setRefusal(result.body && typeof result.body === "object" ? result.body : {});
    return null;
  };

  const approveWaiting = async () => {
    if (!bill || busy) return;
    setBusy(true);
    setRefusal(null);
    const result = await billsApi.approve(org, bill.id);
    if (result.status === 200) {
      fill(result.body);
      setStatus(fm(m.approved, { number: result.body.number }));
    } else setRefusal(result.body && typeof result.body === "object" ? result.body : {});
    setBusy(false);
    setRefresh((n) => n + 1);
  };

  const approveWithVariance = async () => {
    if (!bill || busy) return;
    setBusy(true);
    const result = await billsApi.approve(org, bill.id, true);
    if (result.status === 200) {
      fill(result.body);
      setRefusal(null);
      setStatus(fm(m.approved, { number: result.body.number }));
    } else setRefusal(result.body && typeof result.body === "object" ? result.body : {});
    setBusy(false);
    setRefresh((n) => n + 1);
  };

  const act = async (action: "save" | "submit" | "approve", event?: FormEvent) => {
    event?.preventDefault();
    if (busy || !supplier) return;
    setBusy(true);
    setRefusal(null);
    setStatus("");
    const saved = await save();
    if (saved && action !== "save") {
      const result =
        action === "submit"
          ? await billsApi.submit(org, saved.id)
          : await billsApi.approve(org, saved.id);
      if (result.status === 200) {
        fill(result.body);
        setStatus(
          action === "submit" ? fm(m.submitted) : fm(m.approved, { number: result.body.number }),
        );
      } else setRefusal(result.body && typeof result.body === "object" ? result.body : {});
    } else if (saved) setStatus(fm(m.saved));
    setBusy(false);
    setRefresh((n) => n + 1);
  };

  if (failed) {
    return (
      <ErrorState
        title={fm(m.loadFailed)}
        retryLabel={fm(m.retry)}
        onRetry={() => window.location.reload()}
      />
    );
  }
  if (loading) {
    return (
      <div className="grid gap-6 lg:grid-cols-2" aria-busy="true">
        <Skeleton className="h-96" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  const field = "flex flex-col gap-1 text-sm font-medium text-fg";
  const select =
    "min-h-touch-target rounded-md border border-border bg-surface px-2 text-sm text-fg";
  const refusalText =
    refusal?.detail ??
    (Array.isArray(refusal?.supplier_invoice_no) ? refusal?.supplier_invoice_no[0] : undefined) ??
    (refusal ? fm(m.failed) : "");

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]" data-bill-editor="">
      <DocumentPane
        org={org}
        document={document}
        onAttach={(f) => void attach(f)}
        upload={upload}
      />
      <form
        aria-labelledby={`${ids}-title`}
        onSubmit={(event) => void act("save", event)}
        className="flex min-w-0 flex-col gap-5"
        noValidate
      >
        <div className="flex flex-wrap items-center gap-3">
          <h1 id={`${ids}-title`} className="text-2xl font-semibold text-fg">
            {bill?.number
              ? fm(m.title, { number: bill.number })
              : bill
                ? fm(m.draftTitle)
                : fm(m.newTitle)}
          </h1>
          {bill ? <Badge tone="neutral">{fm(statusLabels[bill.status])}</Badge> : null}
          {bill && bill.status !== "draft" ? (
            <span className="text-sm text-fg-muted">
              {fm(m.heldAmountDue, { amount: formatMoney(bill.amount_due, { locale }) })}
            </span>
          ) : null}
        </div>
        {!editable && bill ? (
          <p className="rounded-md bg-surface-info-subtle p-3 text-sm text-fg" role="note">
            {fm(m.readOnly, { status: fm(statusLabels[bill.status]) })}
          </p>
        ) : null}
        <fieldset
          disabled={!editable}
          className="grid gap-4 sm:grid-cols-2"
          aria-label={fm(m.form)}
        >
          <label className={field}>
            {fm(m.supplier)}
            <select
              value={supplier}
              onChange={(e) => setSupplier(e.target.value)}
              required
              className={select}
            >
              <option value="">{fm(m.chooseSupplier)}</option>
              {suppliers.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </label>
          {renderNumber ? (
            renderNumber({
              supplier,
              value: number,
              onChange: setNumber,
              exclude: bill?.id,
              id: `${ids}-number`,
            })
          ) : (
            <label className={field}>
              {fm(m.supplierInvoiceNo)}
              <Input value={number} onChange={(e) => setNumber(e.target.value)} />
            </label>
          )}
          <label className={field}>
            {fm(m.date)}
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
          </label>
          <label className={field}>
            {fm(m.dueDate)}
            <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            <span className="text-xs font-normal text-fg-muted">{fm(m.dueDateHint)}</span>
          </label>
          <label className={field}>
            {fm(m.reference)}
            <Input value={reference} onChange={(e) => setReference(e.target.value)} />
          </label>
          <label className={field}>
            {fm(m.department)}
            <Input value={department} onChange={(e) => setDepartment(e.target.value)} />
          </label>
          <label className={field}>
            {fm(m.taxMode)}
            <select
              value={taxMode}
              onChange={(e) => setTaxMode(e.target.value as TaxMode)}
              className={select}
            >
              <option value="exclusive">{fm(m.taxExclusive)}</option>
              <option value="inclusive">{fm(m.taxInclusive)}</option>
              <option value="no_tax">{fm(m.taxNone)}</option>
            </select>
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className={field}>
              {fm(m.holdback)}
              <select
                value={holdbackType}
                onChange={(e) => setHoldbackType(e.target.value as HoldbackType)}
                className={select}
              >
                <option value="none">{fm(m.holdbackNone)}</option>
                <option value="amount">{fm(m.holdbackAmount)}</option>
                <option value="percent">{fm(m.holdbackPercent)}</option>
              </select>
            </label>
            {holdbackType !== "none" ? (
              <label className={field}>
                {fm(m.holdbackValue)}
                <Input
                  inputMode="decimal"
                  value={holdbackValue}
                  onChange={(e) => setHoldbackValue(e.target.value)}
                />
              </label>
            ) : null}
          </div>
        </fieldset>

        <DocumentLines
          lines={lines}
          onChange={setLines}
          side="purchase"
          date={date}
          accounts={pickerAccounts}
          taxCodes={pickerCodes}
          amounts={calculation.amounts}
          accountDefaults={accountDefaults}
          labels={linesLabels}
          locale={locale}
          readOnly={!editable}
        />

        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <label className={`${field} flex-1`}>
            {fm(m.notes)}
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              disabled={!editable}
              className="rounded-md border border-border bg-surface p-2 text-sm font-normal text-fg"
            />
          </label>
          <div className="flex flex-col gap-2 xl:w-96">
            <DocumentWarnings warnings={calculation.warnings} />
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
            {bill && Number(bill.holdback_amount) > 0 ? (
              <p className="text-sm text-fg-muted" data-holdback="">
                {fm(m.holdbackHeld, { amount: formatMoney(bill.holdback_amount, { locale }) })}
              </p>
            ) : null}
          </div>
        </div>

        {panels ? panels(bill, refresh) : null}

        {refusal ? (
          <p
            role="alert"
            className="rounded-md border border-border-danger p-3 text-sm font-semibold text-fg-danger"
            data-refusal={refusal.code ?? ""}
          >
            {refusalText}
          </p>
        ) : null}
        {refusal?.code === "purchases.bill.variance" ? (
          <div className="flex flex-wrap items-center gap-3" data-variance="">
            <Button variant="primary" disabled={busy} onClick={() => void approveWithVariance()}>
              {fm(matchMessages.approveWithVariance)}
            </Button>
            <span className="text-xs text-fg-muted">{fm(matchMessages.varianceHint)}</span>
          </div>
        ) : null}
        <p role="status" className="text-sm text-fg">
          {status}
        </p>
        {editable ? (
          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={busy || !supplier}>
              {busy ? fm(m.saving) : fm(m.saveDraft)}
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={busy || !supplier}
              onClick={() => void act("submit")}
            >
              {fm(m.submit)}
            </Button>
            <Button
              type="button"
              variant="primary"
              disabled={busy || !supplier}
              onClick={() => void act("approve")}
            >
              {fm(m.approve)}
            </Button>
          </div>
        ) : bill?.status === "awaiting_approval" ? (
          <div className="flex flex-wrap gap-3">
            <Button
              type="button"
              variant="primary"
              disabled={busy}
              onClick={() => void approveWaiting()}
            >
              {fm(routingMessages.approveNow)}
            </Button>
          </div>
        ) : null}
      </form>
    </div>
  );
}
