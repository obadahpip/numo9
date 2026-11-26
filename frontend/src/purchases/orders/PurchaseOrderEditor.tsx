"use client";

/**
 * Purchase order editor (E-01-T11): supplier, order date, reference, tax mode, the shared
 * document grid in its **purchase mode** (D-01: expense/asset accounts, purchase tax codes), the
 * **delivery block** (deliver to, attention, delivery date, instructions), notes and the totals,
 * with a **limit indicator** — the person's purchase-order approval limit against the total as
 * it is typed: within it the main button approves, above it (or with no limit) it submits for
 * approval. An approved PO is still edited (its lines keep their receipts); a higher total sends
 * it back for approval (E-01-T03). Billed, closed and cancelled POs open read-only.
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
import { useCallback, useEffect, useId, useMemo, useState, type FormEvent } from "react";

import { accountsApi, type Account } from "@/accounts/api";
import { pickerAccount } from "@/accounts/picker";
import { pickerTaxCode } from "@/banking/MoneyForm";
import { contactsApi, type ContactSummary } from "@/contacts/api";
import { useDocumentLinesLabels, useDocumentTotalsLabels } from "@/documents/labels";
import { DocumentWarnings } from "@/documents/DocumentWarnings";
import { TaxNotices } from "@/documents/TaxNotices";
import { useDocumentCalculation, type MirrorTaxCode } from "@/documents/useDocumentCalculation";
import { useTaxDefaults } from "@/documents/useTaxDefaults";
import { useFormatMessage } from "@/i18n";
import { taxApi, type TaxCode } from "@/tax/api";

import { billUrl } from "../BillEditor";

import {
  purchaseOrdersApi,
  type PurchaseOrder,
  type PurchaseOrderInput,
  type PurchaseOrderLine,
  type PurchaseOrderStatus,
  type Refusal,
  type TaxMode,
} from "./api";
import { po as m, statusLabels } from "./messages";

const today = () => new Date().toISOString().slice(0, 10);

/** Statuses whose header and lines can still change. */
export const EDITABLE: readonly PurchaseOrderStatus[] = [
  "draft",
  "awaiting_approval",
  "approved",
  "partially_received",
];
const APPROVED: readonly PurchaseOrderStatus[] = ["approved", "partially_received", "received"];
/** Statuses with nothing more to do (no edit, no cancel or close). */
const FINAL: readonly PurchaseOrderStatus[] = ["billed", "closed", "cancelled"];

export function orderUrl(org: string, id: string): string {
  return `/o/${org}/purchases/orders/${id}`;
}

export function gridLine(line: PurchaseOrderLine): DocumentGridLine {
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

/** The lines the server receives; a line loaded from the server keeps its id (its receipts). */
export function orderLines(lines: readonly DocumentGridLine[], known: ReadonlySet<string>) {
  return lines
    .filter((line) => line.account || line.description || Number(line.unitPrice) > 0)
    .map((line) => {
      const discount = parseLineDiscount(line.discount) ?? { type: "none" as const, value: "0" };
      return {
        id: known.has(line.id) ? line.id : null,
        description: line.description,
        quantity: line.quantity || "1",
        unit_price: line.unitPrice || "0",
        discount_type: discount.type,
        discount_value: discount.value,
        account: line.account,
        tax_code: line.taxCode,
      };
    });
}

/** The limit indicator's verdict for a total (CAD) and a limit (`null`: no limit). */
export function limitVerdict(total: string, limit: string | null): "within" | "above" | "none" {
  if (limit === null) return "none";
  return Number(total || "0") <= Number(limit) ? "within" : "above";
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

export interface PurchaseOrderEditorProps {
  org: string;
  /** An existing purchase order; empty for a new one. */
  id?: string;
  navigate?: (href: string) => void;
}

export function PurchaseOrderEditor({ org, id, navigate }: Readonly<PurchaseOrderEditorProps>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const linesLabels = useDocumentLinesLabels("purchase");
  const totalsLabels = useDocumentTotalsLabels();

  const [order, setOrder] = useState<PurchaseOrder | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(Boolean(id));
  const [suppliers, setSuppliers] = useState<ContactSummary[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [codes, setCodes] = useState<TaxCode[]>([]);
  const [limit, setLimit] = useState<string | null>(null);

  const [supplier, setSupplier] = useState("");
  const [date, setDate] = useState(today);
  const [reference, setReference] = useState("");
  const [taxMode, setTaxMode] = useState<TaxMode>("exclusive");
  const [deliveryAddress, setDeliveryAddress] = useState("");
  const [deliveryAttention, setDeliveryAttention] = useState("");
  const [deliveryDate, setDeliveryDate] = useState("");
  const [deliveryInstructions, setDeliveryInstructions] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DocumentGridLine[]>(() => [newDocumentLine()]);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const fill = useCallback((loaded: PurchaseOrder) => {
    setOrder(loaded);
    setSupplier(loaded.supplier.id);
    setDate(loaded.date);
    setReference(loaded.reference);
    setTaxMode(loaded.tax_mode);
    setDeliveryAddress(loaded.delivery_address);
    setDeliveryAttention(loaded.delivery_attention);
    setDeliveryDate(loaded.delivery_date ?? "");
    setDeliveryInstructions(loaded.delivery_instructions);
    setNotes(loaded.notes);
    setLimit(loaded.approval.limit);
    setLines(loaded.lines.length ? loaded.lines.map(gridLine) : [newDocumentLine()]);
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
    if (!id) {
      void purchaseOrdersApi
        .approvalLimit(org)
        .then((r) => setLimit(r.status === 200 ? (r.body.limit ?? null) : null));
      return;
    }
    setLoading(true);
    void purchaseOrdersApi.get(org, id).then((result) => {
      setLoading(false);
      if (result.status === 200 && result.body.id) fill(result.body);
      else setFailed(true);
    });
  }, [org, id, fill]);

  const known = useMemo(() => new Set(order?.lines.map((line) => line.id) ?? []), [order]);
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
    kind: "purchase_order",
    date,
    taxMode,
    discountType: "none",
    discountValue: "0",
    lines,
    taxCodes: useMemo(() => codes.map(mirrorTaxCode), [codes]),
    contact: supplier || null,
  });

  const editable = !order || EDITABLE.includes(order.status);
  const approvedAlready = Boolean(order && APPROVED.includes(order.status));
  const taxDefaults = useTaxDefaults({
    org,
    side: "purchase",
    date,
    contact: supplier || null,
    lines,
    setLines,
    enabled: editable,
  });

  const total = calculation.totals.total;
  const verdict = limitVerdict(total, limit);

  const body = (): PurchaseOrderInput => ({
    supplier,
    date,
    reference,
    tax_mode: taxMode,
    notes,
    delivery_attention: deliveryAttention,
    delivery_address: deliveryAddress,
    delivery_date: deliveryDate || null,
    delivery_instructions: deliveryInstructions,
    lines: orderLines(lines, known),
    ...(order ? { version: order.version } : {}),
  });

  const refuse = (result: { body: unknown }) =>
    setRefusal(result.body && typeof result.body === "object" ? (result.body as Refusal) : {});

  const save = async (): Promise<PurchaseOrder | null> => {
    const result = order
      ? await purchaseOrdersApi.update(org, order.id, body())
      : await purchaseOrdersApi.create(org, body());
    if (result.status === 200 || result.status === 201) {
      fill(result.body);
      if (!order) {
        const href = orderUrl(org, result.body.id);
        if (navigate) navigate(href);
        else window.history.replaceState(null, "", href);
      }
      return result.body;
    }
    refuse(result);
    return null;
  };

  const act = async (action: "save" | "submit" | "approve", event?: FormEvent) => {
    event?.preventDefault();
    if (busy || !supplier) return;
    setBusy(true);
    setRefusal(null);
    setStatus("");
    const before = order?.status;
    const saved = await save();
    if (saved && action !== "save") {
      const result = await purchaseOrdersApi.action(org, saved.id, action);
      if (result.status === 200) {
        fill(result.body);
        setStatus(
          action === "submit" ? fm(m.submitted) : fm(m.approved, { number: result.body.number }),
        );
      } else refuse(result);
    } else if (saved) {
      if (before && APPROVED.includes(before) && saved.status === "awaiting_approval")
        setStatus(fm(m.reapproval));
      else setStatus(saved.status === "draft" ? fm(m.saved) : fm(m.changesSaved));
    }
    setBusy(false);
  };

  const createBill = async () => {
    if (!order || busy) return;
    setBusy(true);
    setRefusal(null);
    const result = await purchaseOrdersApi.billFromOrder(org, order.id);
    setBusy(false);
    if (result.status === 201 && result.body.id) {
      const href = billUrl(org, result.body.id);
      if (navigate) navigate(href);
      else window.location.assign(href);
    } else refuse(result);
  };

  const end = async (action: "cancel" | "close") => {
    if (!order || busy) return;
    setBusy(true);
    setRefusal(null);
    const result = await purchaseOrdersApi.action(org, order.id, action);
    if (result.status === 200) fill(result.body);
    else refuse(result);
    setBusy(false);
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
      <div className="flex flex-col gap-4" aria-busy="true">
        <Skeleton className="h-24" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  const field = "flex flex-col gap-1 text-sm font-medium text-fg";
  const select =
    "min-h-touch-target rounded-md border border-border bg-surface px-2 text-sm text-fg";
  const area = "rounded-md border border-border bg-surface p-2 text-sm font-normal text-fg";
  const lineErrors =
    refusal && typeof refusal.lines === "object" && refusal.lines
      ? Object.values(refusal.lines as Record<string, unknown>)
          .flatMap((value) =>
            Array.isArray(value)
              ? value
              : value && typeof value === "object"
                ? Object.values(value as Record<string, unknown>).flat()
                : [],
          )
          .map(String)
      : [];
  const refusalText = refusal?.detail ?? lineErrors[0] ?? (refusal ? fm(m.failed) : "");
  const canApprove = verdict === "within";
  const ended = order ? FINAL.includes(order.status) : false;

  return (
    <form
      aria-labelledby={`${ids}-title`}
      onSubmit={(event) => void act("save", event)}
      className="flex min-w-0 flex-col gap-5"
      data-po-editor=""
      noValidate
    >
      <div className="flex flex-wrap items-center gap-3">
        <h1 id={`${ids}-title`} className="text-2xl font-semibold text-fg">
          {order?.number
            ? fm(m.title, { number: order.number })
            : order
              ? fm(m.draftTitle)
              : fm(m.newTitle)}
        </h1>
        {order ? <Badge tone="neutral">{fm(statusLabels[order.status])}</Badge> : null}
        {order && order.number ? (
          <a
            href={purchaseOrdersApi.pdfUrl(org, order.id)}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-fg underline"
          >
            {fm(m.pdf)}
          </a>
        ) : null}
        {order && ["approved", "partially_received"].includes(order.status) ? (
          <a
            href={`${orderUrl(org, order.id)}/receive`}
            className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-fg"
            data-receive-link=""
          >
            {fm(m.receive)}
          </a>
        ) : null}
      </div>
      {!editable && order ? (
        <p className="rounded-md bg-surface-info-subtle p-3 text-sm text-fg" role="note">
          {fm(m.readOnly, { status: fm(statusLabels[order.status]) })}
        </p>
      ) : null}
      <fieldset disabled={!editable} className="grid gap-4 sm:grid-cols-2" aria-label={fm(m.form)}>
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
        <label className={field}>
          {fm(m.date)}
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
        <label className={field}>
          {fm(m.reference)}
          <Input value={reference} onChange={(e) => setReference(e.target.value)} />
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
      </fieldset>

      <fieldset
        disabled={!editable}
        className="grid gap-4 rounded-lg border border-border p-4 sm:grid-cols-2"
        data-delivery=""
      >
        <legend className="px-1 text-sm font-semibold text-fg">{fm(m.delivery)}</legend>
        <label className={`${field} sm:row-span-2`}>
          {fm(m.deliveryAddress)}
          <textarea
            value={deliveryAddress}
            onChange={(e) => setDeliveryAddress(e.target.value)}
            rows={3}
            className={area}
          />
        </label>
        <label className={field}>
          {fm(m.deliveryAttention)}
          <Input value={deliveryAttention} onChange={(e) => setDeliveryAttention(e.target.value)} />
        </label>
        <label className={field}>
          {fm(m.deliveryDate)}
          <Input
            type="date"
            value={deliveryDate}
            onChange={(e) => setDeliveryDate(e.target.value)}
          />
        </label>
        <label className={`${field} sm:col-span-2`}>
          {fm(m.deliveryInstructions)}
          <textarea
            value={deliveryInstructions}
            onChange={(e) => setDeliveryInstructions(e.target.value)}
            rows={2}
            className={area}
          />
        </label>
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
        taxWhy={taxDefaults.taxWhy}
        taxAuto={taxDefaults.taxAuto}
        taxOverridden={taxDefaults.taxOverridden}
        onResetTax={taxDefaults.reset}
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
            className={area}
          />
        </label>
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
          {editable ? (
            <p
              role="status"
              aria-label={fm(m.limitTitle)}
              data-limit={verdict}
              className={`rounded-md p-2 text-sm ${
                verdict === "within"
                  ? "bg-surface-success-subtle text-fg"
                  : "bg-surface-warning-subtle text-fg"
              }`}
            >
              {verdict === "none"
                ? fm(m.limitNone)
                : verdict === "within"
                  ? fm(m.limitWithin, { limit: formatMoney(limit ?? "0", { locale }) })
                  : fm(m.limitAbove, {
                      total: formatMoney(total || "0", { locale }),
                      limit: formatMoney(limit ?? "0", { locale }),
                    })}
            </p>
          ) : null}
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
        {status}
      </p>
      <div className="flex flex-wrap gap-3">
        {editable && !approvedAlready ? (
          <>
            <Button type="submit" disabled={busy || !supplier}>
              {busy ? fm(m.saving) : fm(m.saveDraft)}
            </Button>
            {canApprove ? (
              <Button
                type="button"
                variant="primary"
                disabled={busy || !supplier}
                onClick={() => void act("approve")}
              >
                {fm(m.approve)}
              </Button>
            ) : order?.status !== "awaiting_approval" ? (
              <Button
                type="button"
                variant="primary"
                disabled={busy || !supplier}
                onClick={() => void act("submit")}
              >
                {fm(m.submit)}
              </Button>
            ) : null}
          </>
        ) : null}
        {editable && approvedAlready ? (
          <Button type="submit" variant="primary" disabled={busy}>
            {busy ? fm(m.saving) : fm(m.saveChanges)}
          </Button>
        ) : null}
        {order && APPROVED.includes(order.status) ? (
          <Button
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={() => void createBill()}
          >
            {fm(m.createBill)}
          </Button>
        ) : null}
        {order && order.status !== "draft" && !ended ? (
          <Button
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={() => void end(order.status === "received" ? "close" : "cancel")}
          >
            {order.status === "received" ? fm(m.close) : fm(m.cancel)}
          </Button>
        ) : null}
      </div>
    </form>
  );
}
