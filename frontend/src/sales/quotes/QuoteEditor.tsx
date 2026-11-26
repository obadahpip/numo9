"use client";

/**
 * Quote editor (D-02-T12), `/o/:org/sales/quotes/new` and `/o/:org/sales/quotes/:id`: the header
 * (customer, quote date, **expiry date** — 30 days ahead by default —, title, reference, tax
 * mode, the **deposit** asked on acceptance: none, an amount or a % of the accepted total, and a
 * summary), the shared document grid (D-01, sales side) with the quote's own columns — an
 * **Optional** toggle, an **Alternative group** picker (type a group name or pick one already
 * used; lines of a group are alternatives) and **Included** (which optional lines and which
 * alternative are chosen to start with) — and the live totals of the lines that count (the same
 * rule as the server, D-02-T03). A quote that isn't a draft opens read-only, with its links:
 * revision, deposit invoice, invoice, acceptance evidence. The action bar comes in through
 * `actions` (`QuoteActionBar`).
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
  type AppLocale,
  type DocumentGridLine,
  type LineColumn,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import Link from "next/link";
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
import { useFormatMessage } from "@/i18n";
import { taxApi, type TaxCode } from "@/tax/api";

import type { Refusal, TaxMode } from "../invoices/api";
import { statusLabels } from "../invoices/messages";
import { quoteUrl, quotesApi, type DepositType, type Quote, type QuoteInput } from "./api";
import {
  alternativeGroups,
  countedLines,
  newQuoteLine,
  normaliseQuoteLines,
  quoteGridLine,
  quoteLines,
  type QuoteGridLine,
} from "./lines";
import { qm, quoteStatusLabels } from "./messages";

const today = () => new Date().toISOString().slice(0, 10);
export const VALID_DAYS = 30;

export function plusDays(date: string, days: number): string {
  const day = new Date(`${date}T12:00:00Z`);
  if (Number.isNaN(day.getTime())) return "";
  day.setUTCDate(day.getUTCDate() + days);
  return day.toISOString().slice(0, 10);
}

/** The deposit asked at a total, to the cent (the server's rule: never more than the total). */
export function depositAt(type: DepositType, value: string, total: string): number {
  const amount = Number(value) || 0;
  const whole = Number(total) || 0;
  const asked = type === "percent" ? (whole * amount) / 100 : type === "amount" ? amount : 0;
  return Math.max(0, Math.min(Math.round(asked * 100) / 100, whole));
}

function mirrorTaxCode(code: TaxCode): MirrorTaxCode {
  return {
    id: code.id,
    components: code.components.map((c) => ({ key: c.key, name: c.name, rate: c.rate })),
  };
}

/** What the action bar works with. */
export interface QuoteActionContext {
  quote: Quote | null;
  busy: boolean;
  /** Save the form (create or update a draft); the saved quote, or null when refused. */
  save: (stay?: boolean) => Promise<Quote | null>;
  open: (quote: Quote) => void;
  show: (quote: Quote, notice?: string) => void;
  refuse: (refusal: Refusal) => void;
  notify: (notice: string) => void;
  setBusy: (busy: boolean) => void;
  ready: boolean;
}

export interface QuoteEditorProps {
  org: string;
  id?: string;
  navigate?: (href: string) => void;
  actions?: (context: QuoteActionContext) => ReactNode;
}

export function QuoteEditor({ org, id, navigate, actions }: Readonly<QuoteEditorProps>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const linesLabels = useDocumentLinesLabels("sales");
  const totalsLabels = useDocumentTotalsLabels();

  const [quote, setQuote] = useState<Quote | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(Boolean(id));
  const [customers, setCustomers] = useState<ContactSummary[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [codes, setCodes] = useState<TaxCode[]>([]);

  const [customer, setCustomer] = useState("");
  const [date, setDate] = useState(today);
  const [expiry, setExpiry] = useState(() => plusDays(today(), VALID_DAYS));
  const [expiryTouched, setExpiryTouched] = useState(false);
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [reference, setReference] = useState("");
  const [taxMode, setTaxMode] = useState<TaxMode>("exclusive");
  const [depositType, setDepositType] = useState<DepositType>("none");
  const [depositValue, setDepositValue] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLinesRaw] = useState<QuoteGridLine[]>(() => [newQuoteLine()]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const setLines = useCallback(
    (next: DocumentGridLine[] | ((current: DocumentGridLine[]) => DocumentGridLine[])) =>
      setLinesRaw((current) =>
        normaliseQuoteLines(
          (typeof next === "function" ? next(current) : next) as QuoteGridLine[],
          current,
        ),
      ),
    [],
  );

  const fill = useCallback((loaded: Quote) => {
    setQuote(loaded);
    setCustomer(loaded.customer.id);
    setDate(loaded.date);
    setExpiry(loaded.expiry_date);
    setExpiryTouched(true);
    setTitle(loaded.title);
    setSummary(loaded.summary);
    setReference(loaded.reference);
    setTaxMode(loaded.tax_mode);
    setDepositType(loaded.deposit_type);
    setDepositValue(loaded.deposit_type === "none" ? "" : String(Number(loaded.deposit_value)));
    setNotes(loaded.notes);
    setLinesRaw(loaded.lines.length ? loaded.lines.map(quoteGridLine) : [newQuoteLine()]);
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
    void quotesApi.get(org, id).then((result) => {
      setLoading(false);
      if (result.status === 200 && result.body.id) fill(result.body);
      else setFailed(true);
    });
  }, [org, id, fill]);

  // A new quote's first line starts on the first revenue account (as invoices, D-03a-T13).
  const revenue = useMemo(() => accounts.filter((a) => a.type === "revenue"), [accounts]);
  useEffect(() => {
    if (id || !revenue[0]) return;
    const first = revenue[0].id;
    setLinesRaw((current) => {
      const [only] = current;
      return current.length === 1 && only && !only.account
        ? [{ ...only, account: first }]
        : current;
    });
  }, [id, revenue]);

  const changeDate = (value: string) => {
    setDate(value);
    if (!expiryTouched) setExpiry(plusDays(value, VALID_DAYS));
  };

  const pickerAccounts = useMemo(() => accounts.map(pickerAccount), [accounts]);
  const pickerCodes = useMemo(() => codes.map(pickerTaxCode), [codes]);
  const mirrorCodes = useMemo(() => codes.map(mirrorTaxCode), [codes]);
  const accountDefaults = useMemo(
    () =>
      Object.fromEntries(
        accounts.filter((a) => a.default_tax_key).map((a) => [a.id, a.default_tax_key]),
      ),
    [accounts],
  );
  const flags = useMemo(() => countedLines(lines), [lines]);
  const included = useMemo(() => lines.filter((_l, i) => flags[i]), [lines, flags]);
  const excluded = useMemo(() => lines.filter((_l, i) => !flags[i]), [lines, flags]);
  const common = {
    org,
    side: "sales" as const,
    kind: "quote",
    date,
    taxMode,
    discountType: "none" as const,
    discountValue: "0",
    taxCodes: mirrorCodes,
    contact: customer || null,
  };
  // The totals cover the lines that count; the others still show their own amounts.
  const calculation = useDocumentCalculation({ ...common, lines: included });
  const others = useDocumentCalculation({ ...common, lines: excluded });
  const amounts = useMemo(
    () => ({ ...others.amounts, ...calculation.amounts }),
    [others.amounts, calculation.amounts],
  );

  const editable = !quote || quote.status === "draft";
  const taxDefaults = useTaxDefaults({
    org,
    side: "sales",
    date,
    contact: customer || null,
    lines,
    setLines,
    enabled: editable,
  });

  const groups = alternativeGroups(lines);
  const extraColumns: LineColumn[] = [
    {
      id: "isOptional",
      header: fm(qm.optional),
      kind: "custom",
      width: 84,
      render: ({ id: cell, label, value, onChange, onKeyDown, line }) => (
        <div className="flex min-h-10 items-center justify-center">
          <input
            id={cell}
            type="checkbox"
            aria-label={label}
            checked={Boolean(value)}
            disabled={!editable || Boolean((line as QuoteGridLine).alternativeGroup)}
            onChange={(event) => onChange(event.target.checked)}
            onKeyDown={onKeyDown}
            className="size-5 accent-[var(--color-fg-accent,currentColor)]"
            data-quote-optional=""
          />
        </div>
      ),
    },
    {
      id: "alternativeGroup",
      header: fm(qm.alternative),
      kind: "custom",
      width: 140,
      render: ({ id: cell, label, value, onChange, onKeyDown, line }) => (
        <input
          id={cell}
          aria-label={label}
          list={`${ids}-groups`}
          autoComplete="off"
          maxLength={40}
          value={(value as string | undefined) ?? ""}
          placeholder={fm(qm.alternativeHint)}
          readOnly={!editable}
          disabled={Boolean((line as QuoteGridLine).isOptional)}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
          className="min-h-10 w-full rounded-sm border border-transparent bg-transparent px-2 text-sm text-fg hover:border-border focus:border-border-strong focus:bg-surface"
          data-quote-group=""
        />
      ),
    },
    {
      id: "selected",
      header: fm(qm.included),
      kind: "custom",
      width: 84,
      render: ({ id: cell, label, onChange, onKeyDown, line, index }) => {
        const row = line as QuoteGridLine;
        const choice = Boolean(row.isOptional || row.alternativeGroup);
        return (
          <div className="flex min-h-10 items-center justify-center">
            <input
              id={cell}
              type="checkbox"
              aria-label={label}
              checked={flags[index] ?? true}
              disabled={!editable || !choice}
              onChange={(event) => onChange(event.target.checked)}
              onKeyDown={onKeyDown}
              className="size-5"
              data-quote-included=""
            />
          </div>
        );
      },
    },
  ];

  const body = (): QuoteInput => ({
    customer,
    date,
    expiry_date: expiry,
    title,
    summary,
    reference,
    tax_mode: taxMode,
    deposit_type: depositType,
    deposit_value: depositType === "none" ? "0" : depositValue || "0",
    notes,
    lines: quoteLines(lines, (line) => Boolean(taxDefaults.taxOverridden?.[line])),
    ...(quote ? { version: quote.version } : {}),
  });

  const show = (loaded: Quote, message = "") => {
    fill(loaded);
    setRefusal(null);
    setNotice(message);
  };

  const open = (saved: Quote) => {
    const href = quoteUrl(org, saved.id);
    if (navigate) navigate(href);
    else window.history.replaceState(null, "", href);
  };

  const save = async (stay = false): Promise<Quote | null> => {
    setRefusal(null);
    const result = quote
      ? await quotesApi.update(org, quote.id, body())
      : await quotesApi.create(org, body());
    if (result.status === 200 || result.status === 201) {
      fill(result.body);
      if (!quote && !stay) open(result.body);
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
    if (saved) setNotice(fm(qm.saved));
    setBusy(false);
  };

  if (failed) {
    return (
      <ErrorState
        title={fm(qm.loadFailed)}
        retryLabel={fm(qm.retry)}
        onRetry={() => window.location.reload()}
      />
    );
  }
  if (loading) return <Skeleton className="h-96" />;

  const field = "flex flex-col gap-1 text-sm font-medium text-fg";
  const select =
    "min-h-touch-target rounded-md border border-border bg-surface px-2 text-sm text-fg";
  const fieldError = refusal ? Object.values(refusal).find(Array.isArray) : undefined;
  const refusalText =
    refusal?.detail ?? (fieldError && typeof fieldError[0] === "string" ? fieldError[0] : "");
  const deposit = depositAt(depositType, depositValue, calculation.totals.total);
  const context: QuoteActionContext = {
    quote,
    busy,
    save,
    open,
    show,
    refuse: (r) => {
      setNotice("");
      setRefusal(r);
    },
    notify: (text) => {
      setRefusal(null);
      setNotice(text);
    },
    setBusy,
    ready: Boolean(customer && expiry),
  };
  const status = quote ? fm(quoteStatusLabels[quote.status]).toLowerCase() : "";

  return (
    <form
      aria-labelledby={`${ids}-title`}
      onSubmit={(event) => {
        event.preventDefault();
        void saveDraft();
      }}
      className="flex min-w-0 max-w-6xl flex-col gap-5"
      data-quote-editor=""
      noValidate
    >
      <div className="flex flex-wrap items-center gap-3">
        <h1 id={`${ids}-title`} className="text-2xl font-semibold text-fg">
          {quote ? fm(qm.title, { number: quote.number }) : fm(qm.newTitle)}
        </h1>
        {quote ? (
          <Badge tone="neutral" data-quote-status={quote.status}>
            {fm(quoteStatusLabels[quote.status])}
          </Badge>
        ) : null}
        {quote?.pdf ? (
          <a href={quote.pdf} target="_blank" rel="noreferrer" className="text-sm underline">
            {fm(qm.pdf)}
          </a>
        ) : null}
      </div>
      <QuoteNotes quote={quote} locale={locale} />
      {!editable && quote ? (
        <p className="rounded-md bg-surface-info-subtle p-3 text-sm text-fg" role="note">
          {quote.status === "invoiced"
            ? fm(qm.readOnlyFinal, { status })
            : fm(qm.readOnly, { status })}
        </p>
      ) : null}
      <fieldset
        disabled={!editable}
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
        aria-label={fm(qm.form)}
      >
        <label className={field}>
          {fm(qm.customer)}
          <select
            value={customer}
            onChange={(e) => setCustomer(e.target.value)}
            required
            className={select}
          >
            <option value="">{fm(qm.chooseCustomer)}</option>
            {customers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.display_name}
              </option>
            ))}
          </select>
        </label>
        <label className={field}>
          {fm(qm.date)}
          <Input type="date" value={date} onChange={(e) => changeDate(e.target.value)} required />
        </label>
        <label className={field}>
          {fm(qm.expiryDate)}
          <Input
            type="date"
            value={expiry}
            min={date}
            onChange={(e) => {
              setExpiryTouched(true);
              setExpiry(e.target.value);
            }}
            required
          />
          <span className="text-xs font-normal text-fg-muted">{fm(qm.expiryHint)}</span>
        </label>
        <label className={field}>
          {fm(qm.reference)}
          <Input value={reference} onChange={(e) => setReference(e.target.value)} />
        </label>
        <label className={`${field} sm:col-span-2`}>
          {fm(qm.heading)}
          <Input value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label className={field}>
          {fm(qm.taxMode)}
          <select
            value={taxMode}
            onChange={(e) => setTaxMode(e.target.value as TaxMode)}
            className={select}
          >
            <option value="exclusive">{fm(qm.taxExclusive)}</option>
            <option value="inclusive">{fm(qm.taxInclusive)}</option>
            <option value="no_tax">{fm(qm.taxNone)}</option>
          </select>
        </label>
        <div className="flex flex-col gap-2">
          <label className={field}>
            {fm(qm.deposit)}
            <select
              value={depositType}
              onChange={(e) => setDepositType(e.target.value as DepositType)}
              className={select}
            >
              <option value="none">{fm(qm.depositNone)}</option>
              <option value="amount">{fm(qm.depositAmount)}</option>
              <option value="percent">{fm(qm.depositPercent)}</option>
            </select>
          </label>
          {depositType !== "none" ? (
            <label className={field}>
              {fm(qm.depositValue, { type: depositType })}
              <Input
                inputMode="decimal"
                value={depositValue}
                onChange={(e) => setDepositValue(e.target.value)}
              />
            </label>
          ) : null}
        </div>
        <label className={`${field} sm:col-span-2 lg:col-span-4`}>
          {fm(qm.summary)}
          <textarea
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            rows={2}
            className="rounded-md border border-border bg-surface p-2 text-sm font-normal text-fg"
          />
        </label>
      </fieldset>
      {depositType !== "none" ? (
        <p className="text-sm text-fg-muted" data-quote-deposit="">
          {fm(qm.depositHint, { amount: formatMoney(deposit.toFixed(2), { locale }) })}
        </p>
      ) : null}

      <datalist id={`${ids}-groups`}>
        {groups.map((group) => (
          <option key={group} value={group} />
        ))}
      </datalist>
      <DocumentLines
        lines={lines}
        onChange={setLines}
        side="sales"
        date={date}
        accounts={pickerAccounts}
        taxCodes={pickerCodes}
        amounts={amounts}
        accountDefaults={accountDefaults}
        taxWhy={taxDefaults.taxWhy}
        taxAuto={taxDefaults.taxAuto}
        taxOverridden={taxDefaults.taxOverridden}
        onResetTax={taxDefaults.reset}
        labels={{ ...linesLabels, grid: fm(qm.lines) }}
        locale={locale}
        readOnly={!editable}
        extraColumns={extraColumns}
      />
      <p className="text-xs text-fg-muted">{fm(qm.optionsHint)}</p>

      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <label className={`${field} flex-1`}>
          {fm(qm.notes)}
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
        </div>
      </div>

      {refusal ? (
        <p
          role="alert"
          className="rounded-md border border-border-danger p-3 text-sm font-semibold text-fg-danger"
          data-refusal={refusal.code ?? ""}
        >
          {refusalText || fm(qm.failed)}
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
            {busy ? fm(qm.saving) : fm(qm.saveDraft)}
          </Button>
        </div>
      ) : null}
    </form>
  );
}

/** What happened to the quote: revision links, deposit invoice, invoice, acceptance, decline. */
function QuoteNotes({ quote, locale }: { quote: Quote | null; locale: AppLocale }) {
  const fm = useFormatMessage();
  if (!quote) return null;
  const items: ReactNode[] = [];
  if (quote.superseded_by)
    items.push(
      <Link key="superseded" href={quote.superseded_by.url} className="underline">
        {fm(qm.supersededBy, { number: quote.superseded_by.number })}
      </Link>,
    );
  if (quote.revises)
    items.push(
      <Link key="revises" href={quote.revises.url} className="underline">
        {fm(qm.revisionOf, { number: quote.revises.number })}
      </Link>,
    );
  if (quote.acceptance)
    items.push(
      <span key="accepted">
        {fm(qm.acceptedBy, {
          name: quote.acceptance.typed_name,
          date: quote.acceptance.accepted_at.slice(0, 10),
          signed: String(quote.acceptance.signed),
          hash: quote.acceptance.pdf_sha256.slice(0, 12),
        })}
      </span>,
    );
  if (quote.status === "declined")
    items.push(
      <span key="declined">{fm(qm.declined, { reason: quote.decline_reason || "none" })}</span>,
    );
  if (quote.deposit_invoice)
    items.push(
      <Link key="deposit" href={quote.deposit_invoice.url} className="underline">
        {fm(qm.depositInvoice, {
          number: quote.deposit_invoice.number || fm(qm.draftNumber),
          total: formatMoney(quote.deposit_invoice.total, { locale }),
          status: fm(
            statusLabels[quote.deposit_invoice.status as keyof typeof statusLabels] ??
              statusLabels.draft,
          ).toLowerCase(),
        })}
      </Link>,
    );
  if (quote.invoice)
    items.push(
      <Link key="invoice" href={quote.invoice.url} className="underline">
        {fm(qm.invoiceLink, { number: quote.invoice.number || fm(qm.draftNumber) })}
      </Link>,
    );
  if (quote.link)
    items.push(<span key="views">{fm(qm.linkViews, { views: quote.link.views })}</span>);
  if (!items.length) return null;
  return (
    <ul className="flex flex-col gap-1 text-sm text-fg" data-quote-notes="">
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ul>
  );
}
