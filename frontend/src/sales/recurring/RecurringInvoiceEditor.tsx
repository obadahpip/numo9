"use client";

/**
 * Recurring invoice template editor (D-04-T08), `/o/:org/sales/recurring-invoices/new` and
 * `/o/:org/sales/recurring-invoices/:id`: the invoice editor's header (customer, reference, tax
 * mode) and the **same shared grid** (D-01, sales side), notes, then the **schedule panel** (every
 * N weeks / months / quarters / years from the first invoice date, an optional end, the next 6
 * dates asked of the server — the generator's own engine), the **mode** (save as a draft /
 * approve / approve and send) and **proration** (a partial first or last period charged by days
 * between the service start and end). Placeholders (`{{month}}` …) are listed; a typo the server
 * doesn't know is flagged. Save, then Pause / Resume. The preview of the next invoice (T09) comes
 * in through `aside`.
 */
import {
  Badge,
  Button,
  DocumentLines,
  DocumentTotals,
  ErrorState,
  formatDate,
  Input,
  newDocumentLine,
  Skeleton,
  type AppLocale,
  type DocumentGridLine,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useState, type ReactNode } from "react";

import { accountsApi, type Account } from "@/accounts/api";
import { pickerAccount } from "@/accounts/picker";
import { pickerTaxCode } from "@/banking/MoneyForm";
import { contactsApi, type ContactSummary } from "@/contacts/api";
import { useDebounced } from "@/directory/useDebounced";
import { DocumentWarnings } from "@/documents/DocumentWarnings";
import { useDocumentLinesLabels, useDocumentTotalsLabels } from "@/documents/labels";
import { useDocumentCalculation, type MirrorTaxCode } from "@/documents/useDocumentCalculation";
import { useFormatMessage } from "@/i18n";
import { buildRule, readRule, type Frequency } from "@/journals/recurring/api";
import { taxApi, type TaxCode } from "@/tax/api";

import type { Refusal, TaxMode } from "../invoices/api";
import { gridLine, invoiceLines } from "../invoices/InvoiceEditor";
import {
  recurringInvoicesApi,
  recurringUrl,
  type RecurringInput,
  type RecurringMode,
  type RecurringTemplate,
} from "./api";
import { rim } from "./messages";

export const SCHEDULE_DEBOUNCE_MS = 300;
const NEXT_DATES = 6;
const MODES: readonly RecurringMode[] = ["draft", "approve", "approve_send"];
const FREQUENCIES: readonly Frequency[] = ["weekly", "monthly", "quarterly", "yearly"];
/** What the generator resolves (backend `placeholders.NAMES`) — shown, never translated. */
export const PLACEHOLDERS = ["{{month}}", "{{year}}", "{{period_start}}", "{{period_end}}"];
const today = () => new Date().toISOString().slice(0, 10);

function mirrorTaxCode(code: TaxCode): MirrorTaxCode {
  return {
    id: code.id,
    components: code.components.map((c) => ({ key: c.key, name: c.name, rate: c.rate })),
  };
}

function firstError(body: Refusal | undefined): string | null {
  if (!body) return null;
  if (typeof body.detail === "string") return body.detail;
  for (const [key, value] of Object.entries(body)) {
    if (key !== "code" && Array.isArray(value) && typeof value[0] === "string") return value[0];
  }
  return null;
}

export interface RecurringEditorProps {
  org: string;
  /** An existing template; empty for a new one. */
  id?: string;
  navigate?: (href: string) => void;
  /** The preview of the next invoice (T09), for the saved template. */
  aside?: (template: RecurringTemplate, refresh: number) => ReactNode;
}

export function RecurringInvoiceEditor({
  org,
  id,
  navigate,
  aside,
}: Readonly<RecurringEditorProps>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const linesLabels = useDocumentLinesLabels("sales");
  const totalsLabels = useDocumentTotalsLabels();

  const [template, setTemplate] = useState<RecurringTemplate | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(Boolean(id));
  const [customers, setCustomers] = useState<ContactSummary[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [codes, setCodes] = useState<TaxCode[]>([]);

  const [name, setName] = useState("");
  const [customer, setCustomer] = useState("");
  const [reference, setReference] = useState("");
  const [taxMode, setTaxMode] = useState<TaxMode>("exclusive");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<DocumentGridLine[]>(() => [newDocumentLine()]);
  const [frequency, setFrequency] = useState<Frequency>("monthly");
  const [every, setEvery] = useState(1);
  const [start, setStart] = useState(today);
  const [end, setEnd] = useState("");
  const [mode, setMode] = useState<RecurringMode>("draft");
  const [prorate, setProrate] = useState(false);
  const [serviceStart, setServiceStart] = useState("");
  const [serviceEnd, setServiceEnd] = useState("");

  const [dates, setDates] = useState<string[] | null>(null);
  const [scheduleError, setScheduleError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [refresh, setRefresh] = useState(0);

  const fill = useCallback((loaded: RecurringTemplate) => {
    const rule = readRule(loaded.rrule);
    setTemplate(loaded);
    setName(loaded.name);
    setCustomer(loaded.customer.id);
    setReference(loaded.reference);
    setTaxMode(loaded.tax_mode);
    setNotes(loaded.notes);
    setLines(loaded.lines.length ? loaded.lines.map(gridLine) : [newDocumentLine()]);
    setFrequency(rule.frequency);
    setEvery(rule.every);
    setStart(loaded.start_date);
    setEnd(loaded.end_date ?? "");
    setMode(loaded.mode);
    setProrate(loaded.prorate);
    setServiceStart(loaded.service_start ?? "");
    setServiceEnd(loaded.service_end ?? "");
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
      .codes(org, { side: "sales", date: start })
      .then((r) => setCodes(r.status === 200 ? r.body.results : []))
      .catch(() => setCodes([]));
  }, [org, start]);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    void recurringInvoicesApi.get(org, id).then((result) => {
      setLoading(false);
      if (result.status === 200 && result.body.id) fill(result.body);
      else setFailed(true);
    });
  }, [org, id, fill]);

  // A new template's first line starts on the first revenue account (as the invoice editor).
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

  const rrule = buildRule(frequency, every);
  const scheduleKey = useDebounced(JSON.stringify([rrule, start, end]), SCHEDULE_DEBOUNCE_MS);
  useEffect(() => {
    const [rule, first, last] = JSON.parse(scheduleKey) as [string, string, string];
    if (!first) return;
    let current = true;
    void recurringInvoicesApi
      .schedule(org, { rrule: rule, start_date: first, end_date: last || null, count: NEXT_DATES })
      .then((r) => {
        if (!current) return;
        if (r.status === 200) {
          setDates(r.body.dates);
          setScheduleError(null);
        } else {
          setDates(null);
          setScheduleError(firstError(r.body) ?? fm(rim.saveFailed));
        }
      })
      .catch(() => undefined);
    return () => {
      current = false;
    };
  }, [org, scheduleKey, fm]);

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
    date: start,
    taxMode,
    discountType: "none",
    discountValue: "0",
    lines,
    taxCodes: useMemo(() => codes.map(mirrorTaxCode), [codes]),
    contact: customer || null,
  });

  const body = (): RecurringInput => ({
    name: name.trim(),
    customer,
    reference,
    tax_mode: taxMode,
    notes,
    rrule,
    start_date: start,
    end_date: end || null,
    mode,
    prorate,
    service_start: prorate && serviceStart ? serviceStart : null,
    service_end: prorate && serviceEnd ? serviceEnd : null,
    paused: template?.paused ?? false,
    lines: invoiceLines(lines),
    ...(template ? { version: template.version } : {}),
  });

  const ready = Boolean(name.trim() && customer && start);

  const save = async () => {
    if (busy || !ready) return;
    setBusy(true);
    setNotice("");
    setRefusal(null);
    const result = template
      ? await recurringInvoicesApi.update(org, template.id, body())
      : await recurringInvoicesApi.create(org, body());
    setBusy(false);
    if (result.status === 200 || result.status === 201) {
      fill(result.body);
      setRefresh((n) => n + 1);
      setNotice(fm(rim.saved));
      if (!template) {
        const href = recurringUrl(org, result.body.id);
        if (navigate) navigate(href);
        else window.history.replaceState(null, "", href);
      }
      return;
    }
    setRefusal(result.body && typeof result.body === "object" ? result.body : {});
  };

  const togglePause = async () => {
    if (!template || busy) return;
    setBusy(true);
    const result = template.paused
      ? await recurringInvoicesApi.resume(org, template.id)
      : await recurringInvoicesApi.pause(org, template.id);
    setBusy(false);
    if (result.status === 200) {
      fill(result.body);
      setRefresh((n) => n + 1);
    } else setRefusal(result.body);
  };

  if (failed) {
    return (
      <ErrorState
        title={fm(rim.loadFailed)}
        retryLabel={fm(rim.retry)}
        onRetry={() => window.location.reload()}
      />
    );
  }
  if (loading) return <Skeleton className="h-96" />;

  const field = "flex flex-col gap-1 text-sm font-medium text-fg";
  const hint = "text-xs font-normal text-fg-muted";
  const select =
    "min-h-touch-target rounded-md border border-border bg-surface px-2 text-sm text-fg";

  return (
    <form
      aria-labelledby={`${ids}-title`}
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
      className="flex min-w-0 max-w-6xl flex-col gap-5"
      data-recurring-invoice-editor=""
      noValidate
    >
      <div className="flex flex-wrap items-center gap-3">
        <h1 id={`${ids}-title`} className="text-2xl font-semibold text-fg">
          {template ? fm(rim.title, { name: template.name }) : fm(rim.newTitle)}
        </h1>
        {template ? (
          <Badge tone={template.status === "active" ? "success" : "neutral"}>
            {fm(rim.status, { status: template.status })}
          </Badge>
        ) : null}
      </div>
      {template?.paused ? (
        <p className="rounded-md bg-surface-info-subtle p-3 text-sm text-fg" role="note">
          {fm(rim.pausedNotice)}
        </p>
      ) : null}

      <fieldset className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label={fm(rim.form)}>
        <label className={field}>
          {fm(rim.name)}
          <Input value={name} onChange={(e) => setName(e.target.value)} required />
          <span className={hint}>{fm(rim.nameHint)}</span>
        </label>
        <label className={field}>
          {fm(rim.customer)}
          <select
            value={customer}
            onChange={(e) => setCustomer(e.target.value)}
            required
            className={select}
          >
            <option value="">{fm(rim.chooseCustomer)}</option>
            {customers.map((item) => (
              <option key={item.id} value={item.id}>
                {item.display_name}
              </option>
            ))}
          </select>
        </label>
        <label className={field}>
          {fm(rim.reference)}
          <Input value={reference} onChange={(e) => setReference(e.target.value)} />
        </label>
        <label className={field}>
          {fm(rim.taxMode)}
          <select
            value={taxMode}
            onChange={(e) => setTaxMode(e.target.value as TaxMode)}
            className={select}
          >
            <option value="exclusive">{fm(rim.taxExclusive)}</option>
            <option value="inclusive">{fm(rim.taxInclusive)}</option>
            <option value="no_tax">{fm(rim.taxNone)}</option>
          </select>
        </label>
      </fieldset>

      <p className="flex flex-wrap items-center gap-2 text-sm text-fg-muted" data-placeholders="">
        {fm(rim.placeholders)}
        {PLACEHOLDERS.map((token) => (
          <code key={token} className="rounded bg-surface-muted px-1.5 py-0.5 text-fg">
            {token}
          </code>
        ))}
      </p>
      {template?.unknown_placeholders.length ? (
        <p role="alert" className="text-sm text-fg-warning" data-unknown-placeholders="">
          {fm(rim.unknownPlaceholders, { names: template.unknown_placeholders.join(", ") })}
        </p>
      ) : null}

      <DocumentLines
        lines={lines}
        onChange={setLines}
        side="sales"
        date={start}
        accounts={pickerAccounts}
        taxCodes={pickerCodes}
        amounts={calculation.amounts}
        accountDefaults={accountDefaults}
        labels={linesLabels}
        locale={locale}
      />

      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="flex flex-1 flex-col gap-4">
          <label className={field}>
            {fm(rim.notes)}
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="rounded-md border border-border bg-surface p-2 text-sm font-normal text-fg"
            />
          </label>

          <fieldset
            className="flex flex-col gap-3 rounded-md border border-border p-4"
            data-schedule-panel=""
          >
            <legend className="px-1 text-sm font-semibold text-fg">{fm(rim.schedule)}</legend>
            <div className="flex flex-wrap items-end gap-3">
              <label className={field}>
                {fm(rim.repeatEvery)}
                <Input
                  type="number"
                  min={1}
                  max={99}
                  className="w-20"
                  value={String(every)}
                  onChange={(e) => setEvery(Number(e.target.value) || 1)}
                />
              </label>
              <label className={field}>
                {fm(rim.unit)}
                <select
                  value={frequency}
                  onChange={(e) => setFrequency(e.target.value as Frequency)}
                  className={select}
                >
                  {FREQUENCIES.map((f) => (
                    <option key={f} value={f}>
                      {fm(rim.unitName, { frequency: f })}
                    </option>
                  ))}
                </select>
              </label>
              <label className={field}>
                {fm(rim.start)}
                <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
              </label>
              <label className={field}>
                {fm(rim.end)}
                <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
              </label>
            </div>
            <p className={hint}>{fm(rim.dueRule)}</p>
            <section aria-labelledby={`${ids}-dates`}>
              <h2 id={`${ids}-dates`} className="text-sm font-semibold text-fg">
                {fm(rim.nextDates, { count: NEXT_DATES })}
              </h2>
              {scheduleError ? (
                <p role="alert" className="text-sm text-fg-danger">
                  {scheduleError}
                </p>
              ) : dates && dates.length === 0 ? (
                <p className="text-sm text-fg-muted">{fm(rim.noDates)}</p>
              ) : (
                <ol className="mt-1 flex flex-wrap gap-2 text-sm" aria-live="polite">
                  {(dates ?? []).map((day) => (
                    <li
                      key={day}
                      data-date={day}
                      className="rounded-full bg-surface-muted px-3 py-1 tabular-nums"
                    >
                      {formatDate(day, { locale })}
                    </li>
                  ))}
                </ol>
              )}
            </section>

            <fieldset className="flex flex-col gap-2" data-mode="">
              <legend className="text-sm font-semibold text-fg">{fm(rim.mode)}</legend>
              {MODES.map((option) => (
                <label key={option} className="flex items-start gap-2 text-sm text-fg">
                  <input
                    type="radio"
                    name={`${ids}-mode`}
                    value={option}
                    checked={mode === option}
                    onChange={() => setMode(option)}
                    className="mt-1"
                  />
                  <span className="flex flex-col">
                    <span className="font-medium">{fm(rim.modeName, { mode: option })}</span>
                    <span className={hint}>{fm(rim.modeHint, { mode: option })}</span>
                  </span>
                </label>
              ))}
            </fieldset>

            <fieldset className="flex flex-col gap-2" data-proration="">
              <label className="flex items-center gap-2 text-sm font-medium text-fg">
                <input
                  type="checkbox"
                  checked={prorate}
                  onChange={(e) => setProrate(e.target.checked)}
                />
                {fm(rim.prorate)}
              </label>
              {prorate ? (
                <div className="flex flex-wrap gap-3">
                  <label className={field}>
                    {fm(rim.serviceStart)}
                    <Input
                      type="date"
                      value={serviceStart}
                      onChange={(e) => setServiceStart(e.target.value)}
                    />
                  </label>
                  <label className={field}>
                    {fm(rim.serviceEnd)}
                    <Input
                      type="date"
                      value={serviceEnd}
                      onChange={(e) => setServiceEnd(e.target.value)}
                    />
                  </label>
                </div>
              ) : null}
              <p className={hint}>{fm(rim.prorateHint)}</p>
            </fieldset>
          </fieldset>
        </div>
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
          {template && aside ? aside(template, refresh) : null}
        </div>
      </div>

      {refusal ? (
        <p
          role="alert"
          className="rounded-md border border-border-danger p-3 text-sm font-semibold text-fg-danger"
          data-refusal={refusal.code ?? ""}
        >
          {firstError(refusal) ?? fm(rim.saveFailed)}
        </p>
      ) : null}
      <p role="status" className="text-sm text-fg">
        {notice}
      </p>
      <div className="flex flex-wrap gap-3">
        <Button type="submit" variant="primary" disabled={busy || !ready}>
          {busy ? fm(rim.saving) : fm(rim.save)}
        </Button>
        {template && template.status !== "ended" ? (
          <Button
            type="button"
            variant="secondary"
            disabled={busy}
            onClick={() => void togglePause()}
          >
            {template.paused ? fm(rim.resume) : fm(rim.pause)}
          </Button>
        ) : null}
      </div>
    </form>
  );
}
