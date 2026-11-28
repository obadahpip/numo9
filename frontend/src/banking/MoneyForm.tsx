"use client";

/**
 * Spend money / Receive money (F-01-T10), `/o/:org/banking/spend|receive?account=<bank>`: the
 * shared document grid (D-01) in **bank mode** — a line is an account, a description, a tax code
 * and an amount. Spend lines are purchases (expense and asset accounts, purchase tax codes only);
 * receive lines are sales (revenue accounts, sales codes only) — the same rules as the server
 * (gap-07). The figures are the D-01 calculator's (mirror at once, server after a pause); the
 * contact is optional unless a line's account requires one; documents are dropped on the zone.
 * Posting needs no feed, import or reconciliation (gap-27).
 */
import {
  Button,
  DocumentLines,
  reasonIsEnough,
  DocumentTotals,
  ErrorState,
  Input,
  newDocumentLine,
  type AppLocale,
  type DocumentGridLine,
  type PickerTaxCode,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";

import { accountsApi, type Account } from "@/accounts/api";
import { pickerAccount } from "@/accounts/picker";
import { contactsApi, type ContactSummary } from "@/contacts/api";
import { useDocumentLinesLabels, useDocumentTotalsLabels } from "@/documents/labels";
import { TaxNotices } from "@/documents/TaxNotices";
import { useTaxDefaults } from "@/documents/useTaxDefaults";
import { useDocumentCalculation, type MirrorTaxCode } from "@/documents/useDocumentCalculation";
import type { FileDocument } from "@/files/api";
import { uploadFile } from "@/files/upload";
import { useFormatMessage } from "@/i18n";
import { taxApi, type TaxCode } from "@/tax/api";

import {
  bankingApi,
  type BankAccount,
  type BankTransactionKind,
  type MoneyLineInput,
  type NewBankTransaction,
  type Refusal,
  type TaxMode,
} from "./api";
import { cash } from "./cashControlMessages";
import { money as mm } from "./messages";
import { NegativeBalanceNotice, negativeState } from "./NegativeBalanceNotice";

const today = () => new Date().toISOString().slice(0, 10);
/** The shortest reason an adviser may give to take the account below zero (C-03-T08). */
const MIN_REASON = 10;

export function pickerTaxCode(code: TaxCode): PickerTaxCode {
  return {
    id: code.id,
    code: code.code,
    name: code.name,
    side: code.side,
    type: code.type,
    effective_from: code.effective_from,
    effective_to: code.effective_to,
    archived_at: code.archived_at,
    rate: code.rate,
    detail: code.components.map((c) => `${c.name} ${c.rate} %`).join(" · "),
  };
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

/** The lines the server receives: those with an account and an amount above zero. */
export function moneyLines(
  lines: readonly DocumentGridLine[],
  codes: readonly TaxCode[],
  taxMode: TaxMode,
): MoneyLineInput[] {
  const keyOf = new Map(codes.map((code) => [code.id, code.code]));
  return lines
    .filter((line) => line.account && Number(line.unitPrice) > 0)
    .map((line) => ({
      account: line.account as string,
      amount: Number(line.unitPrice).toFixed(2),
      description: line.description,
      tax_code: taxMode === "no_tax" ? "" : ((line.taxCode && keyOf.get(line.taxCode)) ?? ""),
    }));
}

export interface MoneyFormProps {
  org: string;
  kind: BankTransactionKind;
  /** Bank account preselected (`?account=`). */
  account?: string | null;
  navigate?: (href: string) => void;
}

export function MoneyForm({ org, kind, account: initial, navigate }: Readonly<MoneyFormProps>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const side = kind === "spend" ? "purchase" : "sales";
  const linesLabels = useDocumentLinesLabels(side);
  const totalsLabels = useDocumentTotalsLabels();

  const [banks, setBanks] = useState<BankAccount[] | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [codes, setCodes] = useState<TaxCode[]>([]);
  const [contacts, setContacts] = useState<ContactSummary[]>([]);
  const [loadFailed, setLoadFailed] = useState(false);

  const [bank, setBank] = useState(initial ?? "");
  const [date, setDate] = useState(today);
  const [contact, setContact] = useState("");
  const [reference, setReference] = useState("");
  const [taxMode, setTaxMode] = useState<TaxMode>("exclusive");
  const [lines, setLines] = useState<DocumentGridLine[]>(() => [newDocumentLine()]);
  const [documents, setDocuments] = useState<FileDocument[]>([]);
  const [upload, setUpload] = useState<{ name: string; failed: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState<(Refusal & { adviser?: boolean }) | null>(null);
  const [reason, setReason] = useState("");
  const defaulted = useRef(new Map<string, string>());

  useEffect(() => {
    Promise.all([bankingApi.accounts(org, "active"), accountsApi.list(org, "active")])
      .then(([bankResult, accountResult]) => {
        if (bankResult.status !== 200 || accountResult.status !== 200) {
          setLoadFailed(true);
          return;
        }
        setBanks(bankResult.body.results);
        setBank((current) => current || bankResult.body.results[0]?.id || "");
        setAccounts(accountResult.body.results);
      })
      .catch(() => setLoadFailed(true));
    contactsApi
      .list(org, { status: "active", role: kind === "spend" ? "supplier" : "customer" })
      .then((result) => setContacts(result.status === 200 ? result.body.results : []))
      .catch(() => setContacts([]));
  }, [org, kind]);

  useEffect(() => {
    taxApi
      .codes(org, { side, date })
      .then((result) => setCodes(result.status === 200 ? result.body.results : []))
      .catch(() => setCodes([]));
  }, [org, side, date]);

  // The bank's own ledger account is never a line of its own transaction.
  const bankGl = banks?.find((b) => b.id === bank)?.ledger_account?.id;
  const pickerAccounts = useMemo(
    () => accounts.filter((a) => a.id !== bankGl).map(pickerAccount),
    [accounts, bankGl],
  );
  const pickerCodes = useMemo(() => codes.map(pickerTaxCode), [codes]);
  const accountDefaults = useMemo(
    () =>
      Object.fromEntries(
        accounts.filter((a) => a.default_tax_key).map((a) => [a.id, a.default_tax_key]),
      ),
    [accounts],
  );

  // A line with an account and no tax code gets the server's default (G-02-T09) once.
  useEffect(() => {
    if (taxMode === "no_tax" || !codes.length) return;
    for (const line of lines) {
      if (!line.account || line.taxCode || defaulted.current.get(line.id) === line.account)
        continue;
      defaulted.current.set(line.id, line.account);
      const asked = { id: line.id, account: line.account };
      void bankingApi
        .taxDefault(org, { kind, date, account: asked.account, contact: contact || undefined })
        .then((result) => {
          if (result.status !== 200 || !result.body.code) return;
          const found = codes.find((code) => code.code === result.body.code);
          if (!found) return;
          setLines((rows) =>
            rows.map((row) =>
              row.id === asked.id && row.account === asked.account && !row.taxCode
                ? { ...row, taxCode: found.id }
                : row,
            ),
          );
        })
        .catch(() => undefined);
    }
  }, [org, kind, date, contact, taxMode, lines, codes]);

  const calculation = useDocumentCalculation({
    org,
    side: kind === "spend" ? "purchases" : "sales",
    date,
    taxMode,
    discountType: "none",
    discountValue: "0",
    lines: lines.map((line) => ({ ...line, quantity: "1", discount: "" })),
    taxCodes: useMemo(() => codes.map(mirrorTaxCode), [codes]),
    contact: contact || null,
  });

  const accountOf = (id: string | null) => accounts.find((a) => a.id === id);
  // The inline PST / missing-province warnings (G-02-T08); this form keeps its own defaults.
  const taxNotices = useTaxDefaults({
    org,
    side,
    date,
    contact: contact || null,
    lines,
    setLines,
    apply: false,
  });
  const contactRequired = lines.some((line) => accountOf(line.account)?.require_contact);
  const attachmentRequired = lines.some((line) => accountOf(line.account)?.require_attachment);
  const sent = moneyLines(lines, codes, taxMode);
  const missingContact = contactRequired && !contact;
  const missingDocument = attachmentRequired && documents.length === 0;
  const ready = Boolean(bank) && sent.length > 0 && !missingContact && !missingDocument;

  const attach = async (files: FileList | null) => {
    for (const file of Array.from(files ?? [])) {
      setUpload({ name: file.name, failed: false });
      const state = await uploadFile(org, file, () => undefined);
      if (state.kind === "done") {
        setDocuments((items) => [...items, state.document]);
        setUpload(null);
      } else {
        setUpload({ name: file.name, failed: true });
      }
    }
  };

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    const body: NewBankTransaction = {
      kind,
      bank_account: bank,
      date,
      contact: contact || null,
      reference,
      tax_mode: taxMode,
      lines: sent,
      attachments: documents.map((document) => document.id),
      ...(reason.trim().length >= MIN_REASON ? { override_reason: reason.trim() } : {}),
    };
    const result = await bankingApi.record(org, body).catch(() => null);
    setBusy(false);
    if (result?.status === 201) {
      const href = `/o/${org}/banking/${bank}`;
      if (navigate) navigate(href);
      else window.location.assign(href);
      return;
    }
    setRefusal(
      result && typeof result.body === "object" && result.body
        ? (result.body as Refusal & { adviser?: boolean })
        : { detail: fm(mm.failed) },
    );
  };

  if (loadFailed)
    return (
      <ErrorState
        title={fm(mm.loadFailed)}
        retryLabel={fm(mm.retry)}
        onRetry={() => window.location.reload()}
      />
    );

  // F-07-T07: a negative-balance refusal shows the inline panel (warn: with the reason field).
  const negative = negativeState(refusal?.code);
  const overrideNeeded = negative === "warn";
  const problems = refusal?.errors ?? [];

  return (
    <form
      aria-labelledby={`${ids}-title`}
      onSubmit={(event) => void submit(event)}
      className="flex max-w-6xl flex-col gap-6 p-4"
      data-money-form={kind}
      noValidate
    >
      <h1 id={`${ids}-title`} className="text-2xl font-semibold text-fg">
        {fm(kind === "spend" ? mm.spendTitle : mm.receiveTitle)}
      </h1>
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(mm.bankAccount)}
          <select
            value={bank}
            onChange={(e) => setBank(e.target.value)}
            required
            className="min-h-touch-target rounded-md border border-border bg-surface px-2 text-sm text-fg"
          >
            {(banks ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.display_name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(mm.date)}
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(kind === "spend" ? mm.paidTo : mm.receivedFrom)}
          <select
            value={contact}
            onChange={(e) => setContact(e.target.value)}
            aria-required={contactRequired || undefined}
            aria-invalid={missingContact || undefined}
            data-required={contactRequired ? "true" : undefined}
            className={`min-h-touch-target rounded-md border bg-surface px-2 text-sm text-fg ${
              missingContact ? "border-border-danger" : "border-border"
            }`}
          >
            <option value="">{fm(contactRequired ? mm.chooseContact : mm.noContact)}</option>
            {contacts.map((item) => (
              <option key={item.id} value={item.id}>
                {item.display_name}
              </option>
            ))}
          </select>
          {missingContact ? (
            <span className="text-xs font-medium text-fg-danger" data-contact-required="">
              {fm(mm.contactRequired)}
            </span>
          ) : null}
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(mm.reference)}
          <Input value={reference} onChange={(e) => setReference(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(mm.taxMode)}
          <select
            value={taxMode}
            onChange={(e) => setTaxMode(e.target.value as TaxMode)}
            className="min-h-touch-target rounded-md border border-border bg-surface px-2 text-sm text-fg"
          >
            <option value="exclusive">{fm(mm.taxExclusive)}</option>
            <option value="inclusive">{fm(mm.taxInclusive)}</option>
            <option value="no_tax">{fm(mm.taxNone)}</option>
          </select>
        </label>
      </div>

      <TaxNotices notices={taxNotices.notices} />
      <DocumentLines
        bank
        lines={lines}
        onChange={setLines}
        side={side}
        date={date}
        accounts={pickerAccounts}
        taxCodes={pickerCodes}
        amounts={calculation.amounts}
        accountDefaults={accountDefaults}
        labels={linesLabels}
        locale={locale}
        problems={{}}
      />

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <section
          aria-labelledby={`${ids}-docs`}
          data-attachments=""
          data-required={missingDocument ? "true" : undefined}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            void attach(event.dataTransfer.files);
          }}
          className={`flex flex-1 flex-col gap-2 rounded-md border-2 border-dashed p-4 ${
            missingDocument ? "border-border-danger bg-surface-danger-subtle" : "border-border"
          }`}
        >
          <h2 id={`${ids}-docs`} className="text-sm font-semibold text-fg">
            {fm(mm.attachments)}
          </h2>
          <p className="text-sm text-fg-muted">{fm(mm.attachHint)}</p>
          {missingDocument ? (
            <p className="text-sm font-medium text-fg-danger" data-attachment-required="">
              {fm(mm.attachmentRequired)}
            </p>
          ) : null}
          <label className="w-fit cursor-pointer rounded-md border border-border px-3 py-2 text-sm font-medium text-fg">
            {fm(mm.attachButton)}
            <input
              type="file"
              className="sr-only"
              onChange={(event) => void attach(event.target.files)}
            />
          </label>
          {documents.length ? (
            <ul className="text-sm text-fg">
              {documents.map((document) => (
                <li key={document.id}>{document.name}</li>
              ))}
            </ul>
          ) : null}
          {upload ? (
            <p role="status" className="text-sm text-fg-muted">
              {upload.failed
                ? fm(mm.uploadFailed, { name: upload.name })
                : fm(mm.uploading, { name: upload.name })}
            </p>
          ) : null}
        </section>
        <DocumentTotals
          className="lg:w-96"
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

      {negative && refusal ? (
        <NegativeBalanceNotice
          state={negative}
          shortfalls={refusal.shortfalls ?? []}
          remedies={
            kind === "spend" && bank
              ? [
                  {
                    id: "receive",
                    label: fm(cash.receiveInto),
                    onSelect: () => {
                      const href = `/o/${org}/banking/receive?account=${bank}`;
                      if (navigate) navigate(href);
                      else window.location.assign(href);
                    },
                  },
                ]
              : []
          }
          reason={reason}
          onReasonChange={negative === "warn" ? setReason : undefined}
        />
      ) : refusal ? (
        <section
          role="alert"
          className="rounded-md border border-border-danger p-3 text-sm"
          data-refusal={refusal.code ?? ""}
        >
          <p className="font-semibold text-fg-danger">{refusal.detail ?? fm(mm.failed)}</p>
          {problems.length ? (
            <ul className="mt-1 list-disc ps-5 text-fg">
              {problems.map((problem, i) => (
                <li key={`${problem.code}-${i}`} data-code={problem.code}>
                  {problem.message}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <Button
          type="submit"
          disabled={
            !ready || busy || negative === "block" || (overrideNeeded && !reasonIsEnough(reason))
          }
        >
          {busy ? fm(mm.saving) : fm(kind === "spend" ? mm.saveSpend : mm.saveReceive)}
        </Button>
      </div>
    </form>
  );
}
