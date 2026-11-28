"use client";

/**
 * Manual journal screen (C-03-T11…T14; per-line contact column C-03-T12; C-04-T09 grid: account
 * autocomplete, a difference meter — "Out of balance by $12.50" — with Post disabled until it is
 * $0.00, Tab past the last cell adds a line),
 * `/o/:org/accounting/journals/new`: the header (date,
 * journal type, narration, automatic reversal date), the lines (account, debit, credit,
 * description) and Post / Save as draft. As the journal is typed, the server is asked what it
 * would say (`journals/check`): problems are listed before posting.
 */
import {
  AccountPicker,
  Button,
  Dialog,
  ErrorState,
  formatMoney,
  Input,
  Tooltip,
  type AppLocale,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";

import { accountsApi, type Account } from "@/accounts/api";
import { pickerAccount } from "@/accounts/picker";
import { contactsApi, type ContactSummary } from "@/contacts/api";
import { useDocumentLinesLabels } from "@/documents/labels";
import { useDebounced } from "@/directory/useDebounced";
import type { FileDocument } from "@/files/api";
import { uploadFile } from "@/files/upload";
import { useFormatMessage } from "@/i18n";

import { getJournal } from "../api";
import {
  filledLines,
  SELECTABLE_TYPES,
  writeApi,
  type CheckResult,
  type JournalInput,
  type JournalTypeKey,
  type LineInput,
  type Refusal,
} from "./api";
import { JournalTypePicker } from "./JournalTypePicker";
import { wm } from "./messages";

export const CHECK_DEBOUNCE_MS = 400;
/** The shortest reason an adviser may give to post below zero (server rule, C-03-T08). */
export const MIN_OVERRIDE_REASON = 10;

const emptyLine = (): LineInput => ({
  account: "",
  debit: "",
  credit: "",
  book: "both",
  contact: null,
  description: "",
});

const today = () => new Date().toISOString().slice(0, 10);

function cents(lines: LineInput[], side: "debit" | "credit"): number {
  return lines.reduce((sum, line) => sum + Math.round(Number(line[side] || 0) * 100), 0);
}

function money(lines: LineInput[], side: "debit" | "credit"): string {
  return (cents(lines, side) / 100).toFixed(2);
}

/** Debits − credits in cents (C-04-T09 difference meter): 0 = balanced. */
export function difference(lines: LineInput[]): number {
  return cents(lines, "debit") - cents(lines, "credit");
}

export interface JournalFormProps {
  org: string;
  /** Where a posted or saved journal opens (default: its page). */
  navigate?: (href: string) => void;
  /** Copy journal (C-04-T10): start from this journal's type, narration and lines. */
  copyOf?: string | null;
}

export function JournalForm({ org, navigate, copyOf }: Readonly<JournalFormProps>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const { accountTypes, noAccounts } = useDocumentLinesLabels();
  const headingId = useId();
  const [accounts, setAccounts] = useState<Account[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [date, setDate] = useState(today);
  const [journalType, setJournalType] = useState<JournalTypeKey>("general");
  const [narration, setNarration] = useState("");
  const [autoReverse, setAutoReverse] = useState("");
  const [lines, setLines] = useState<LineInput[]>([emptyLine(), emptyLine()]);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [reason, setReason] = useState("");
  const reasonId = useId();
  const postReasonId = useId();
  const attachId = useId();
  const [documents, setDocuments] = useState<FileDocument[]>([]);
  const [upload, setUpload] = useState<{ name: string; failed: boolean } | null>(null);
  // C-03-T12: the per-line contact column is hidden until asked for, or until an account that
  // requires a contact is chosen (then it opens and the line's contact cell takes focus).
  const [contactColumn, setContactColumn] = useState(false);
  const [contacts, setContacts] = useState<ContactSummary[] | null>(null);
  const [focusContact, setFocusContact] = useState<number | null>(null);
  const contactRefs = useRef<(HTMLSelectElement | null)[]>([]);
  // C-04-T09: Tab past the last cell of the last line adds a line and moves to its account.
  const accountRefs = useRef<(HTMLInputElement | null)[]>([]);
  const [focusAccount, setFocusAccount] = useState<number | null>(null);

  useEffect(() => {
    accountsApi
      .list(org, "active")
      .then((result) => {
        if (result.status === 200) setAccounts(result.body.results.filter((a) => !a.has_children));
        else setLoadFailed(true);
      })
      .catch(() => setLoadFailed(true));
  }, [org]);

  const input: JournalInput = useMemo(
    () => ({
      date,
      journal_type: journalType,
      narration,
      auto_reverse_on: autoReverse || null,
      lines: filledLines(lines),
      attachments: documents.map((document) => document.id),
    }),
    [date, journalType, narration, autoReverse, lines, documents],
  );
  const asked = useDebounced(input, CHECK_DEBOUNCE_MS);

  useEffect(() => {
    if (asked.lines.length < 2) {
      setCheck(null);
      return;
    }
    let current = true;
    writeApi
      .check(org, asked)
      .then((result) => {
        if (current && result.status === 200) setCheck(result.body);
      })
      .catch(() => undefined);
    return () => {
      current = false;
    };
  }, [org, asked]);

  const setLine = (index: number, changes: Partial<LineInput>) =>
    setLines((rows) => rows.map((row, i) => (i === index ? { ...row, ...changes } : row)));

  const accountOf = (id: string) => (accounts ?? []).find((account) => account.id === id);
  const pickerAccounts = useMemo(() => (accounts ?? []).map(pickerAccount), [accounts]);
  // `needs.contact_lines` numbers the filled lines from 1 (the ones sent to the server).
  const filledIndexes = lines.flatMap((line, i) => (filledLines([line]).length ? [i] : []));
  const contactRequired = (line: LineInput, index: number) =>
    Boolean(accountOf(line.account)?.require_contact) ||
    (check?.needs.contact_lines ?? []).includes(filledIndexes.indexOf(index) + 1);
  const contactNeeded = lines.some(contactRequired);
  const showContacts = contactColumn || contactNeeded;

  const chooseAccount = (index: number, accountId: string) => {
    setLine(index, { account: accountId });
    if (accountOf(accountId)?.require_contact && !lines[index]?.contact) setFocusContact(index);
  };

  useEffect(() => {
    if (!showContacts || contacts) return;
    contactsApi
      .list(org, { status: "active" })
      .then((result) => setContacts(result.status === 200 ? result.body.results : []))
      .catch(() => setContacts([]));
  }, [org, showContacts, contacts]);

  useEffect(() => {
    if (focusAccount === null) return;
    accountRefs.current[focusAccount]?.focus();
    setFocusAccount(null);
  }, [focusAccount, lines.length]);

  const tabOut = (index: number) => (event: KeyboardEvent) => {
    if (event.key !== "Tab" || event.shiftKey || index !== lines.length - 1) return;
    event.preventDefault();
    setLines((rows) => [...rows, emptyLine()]);
    setFocusAccount(index + 1);
  };

  useEffect(() => {
    if (focusContact === null) return;
    contactRefs.current[focusContact]?.focus();
    setFocusContact(null);
  }, [focusContact, showContacts]);

  useEffect(() => {
    if (!copyOf) return;
    void getJournal(org, copyOf).then((result) => {
      if (result.status !== 200) return;
      const source = result.body;
      const amount = (value: string) => (Number(value) > 0 ? value : "");
      setLines(
        source.lines.map((line) => ({
          account: line.account.id,
          debit: amount(line.debit),
          credit: amount(line.credit),
          book: line.book,
          contact: line.contact?.id ?? null,
          description: line.description,
        })),
      );
      setNarration(source.narration);
      const kind = source.journal_type as JournalTypeKey | undefined;
      if (kind && (SELECTABLE_TYPES as readonly string[]).includes(kind)) setJournalType(kind);
      if (source.lines.some((line) => line.contact)) setContactColumn(true);
    });
  }, [org, copyOf]);

  const submit = async (post: boolean, overrideReason = "", forApproval = false) => {
    setBusy(true);
    setFailed(false);
    setRefusal(null);
    const body = overrideReason
      ? { ...input, post, override_reason: overrideReason }
      : { ...input, post };
    const result = await writeApi.create(org, body);
    if (result.status === 201 && forApproval) {
      // Submit for approval (C-04-T10): the draft just saved goes to an approver.
      const sent = await writeApi.action(org, result.body.id, "submit");
      if (sent.status !== 200) {
        setBusy(false);
        setRefusal(sent.body);
        return;
      }
    }
    setBusy(false);
    if (result.status === 201) {
      const href = `/o/${org}/accounting/journals/${result.body.id}`;
      if (navigate) navigate(href);
      else window.location.assign(href);
      return;
    }
    // F-07-T04: a negative-balance warning without a reason is a 422 (409 before F-07).
    if (
      (result.status === 422 || result.status === 409) &&
      result.body.code === "ledger.journal.override_reason_required"
    ) {
      setOverrideOpen(true);
      setCheck((c) =>
        c ? { ...c, adviser: true, shortfalls: result.body.shortfalls ?? c.shortfalls } : c,
      );
      return;
    }
    if (result.status === 400 || result.status === 409 || result.status === 422)
      setRefusal(result.body);
    else setFailed(true);
  };

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

  const off = difference(lines);
  const used = lines.some((line) => Number(line.debit) > 0 || Number(line.credit) > 0);
  const unbalanced = off !== 0 || !used;
  const shortfalls = refusal?.shortfalls ?? check?.shortfalls ?? [];
  const adviser = refusal?.adviser ?? check?.adviser ?? false;
  const blocked = shortfalls.length > 0 && !adviser;
  const flagged = lines.some(
    (line) => (accounts ?? []).find((a) => a.id === line.account)?.require_attachment,
  );
  const needsAttachment = documents.length === 0 && (Boolean(check?.needs.attachment) || flagged);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (blocked || needsAttachment || unbalanced) return;
    if (shortfalls.length > 0 && adviser) {
      setOverrideOpen(true);
      return;
    }
    void submit(true);
  };

  if (loadFailed)
    return (
      <ErrorState
        title={fm(wm.failed)}
        retryLabel={fm(wm.retry)}
        onRetry={() => window.location.reload()}
      />
    );
  const problems = refusal?.errors ?? check?.errors ?? [];
  const chipFor = (accountId: string) =>
    shortfalls.find((shortfall) => shortfall.account.id === accountId)?.message;

  return (
    <form
      aria-labelledby={headingId}
      onSubmit={onSubmit}
      className="flex max-w-5xl flex-col gap-6 p-4"
      noValidate
    >
      <h1 id={headingId} className="text-2xl font-semibold text-fg">
        {fm(wm.title)}
      </h1>
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(wm.date)}
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} required />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-fg sm:col-span-2">
          {fm(wm.narration)}
          <Input value={narration} onChange={(e) => setNarration(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(wm.autoReverse)}
          <Input type="date" value={autoReverse} onChange={(e) => setAutoReverse(e.target.value)} />
        </label>
      </div>
      <JournalTypePicker value={journalType} onChange={setJournalType} />

      <section
        aria-labelledby={`${attachId}-title`}
        data-attachments=""
        data-required={needsAttachment ? "true" : undefined}
        onDragOver={(event) => event.preventDefault()}
        onDrop={(event) => {
          event.preventDefault();
          void attach(event.dataTransfer.files);
        }}
        className={`flex flex-col gap-2 rounded-md border-2 border-dashed p-4 ${
          needsAttachment ? "border-border-danger bg-surface-danger-subtle" : "border-border"
        }`}
      >
        <h2 id={`${attachId}-title`} className="text-sm font-semibold text-fg">
          {fm(wm.attachments)}
        </h2>
        <p className="text-sm text-fg-muted">{fm(wm.attachHint)}</p>
        {needsAttachment ? (
          <p className="text-sm font-medium text-fg-danger" data-attachment-required="">
            {fm(wm.attachmentRequired)}
          </p>
        ) : null}
        <label className="w-fit cursor-pointer rounded-md border border-border px-3 py-2 text-sm font-medium text-fg">
          {fm(wm.attachButton)}
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
              ? fm(wm.uploadFailed, { name: upload.name })
              : fm(wm.uploading, { name: upload.name })}
          </p>
        ) : null}
      </section>

      <table className="w-full text-sm">
        <caption className="pb-2 text-start text-lg font-semibold text-fg">{fm(wm.lines)}</caption>
        <thead>
          <tr className="text-start text-xs text-fg-muted">
            <th scope="col" className="w-2/5 py-1 text-start">
              {fm(wm.account)}
            </th>
            <th scope="col" className="py-1 text-end">
              {fm(wm.debit)}
            </th>
            <th scope="col" className="py-1 text-end">
              {fm(wm.credit)}
            </th>
            <th scope="col" className="py-1 text-start">
              {fm(wm.description)}
            </th>
            {showContacts ? (
              <th scope="col" className="py-1 ps-2 text-start" data-column="contact">
                {fm(wm.contact)}
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {lines.map((line, index) => {
            const n = index + 1;
            return (
              <tr key={index} className="border-t border-border align-top" data-line={n}>
                <td className="py-2 pe-2">
                  <AccountPicker
                    ref={(element) => {
                      accountRefs.current[index] = element;
                    }}
                    aria-label={fm(wm.accountOfLine, { line: n })}
                    accounts={pickerAccounts}
                    context="journal"
                    value={line.account || null}
                    onChange={(accountId) => chooseAccount(index, accountId ?? "")}
                    typeLabels={accountTypes}
                    emptyMessage={noAccounts}
                    placeholder={fm(wm.chooseAccount)}
                  />
                  {line.account && chipFor(line.account) ? (
                    <p
                      data-chip="negative-cash"
                      className="mt-1 inline-flex rounded-full bg-surface-danger-subtle px-2 py-0.5 text-xs font-medium text-fg-danger"
                    >
                      {chipFor(line.account)}
                    </p>
                  ) : null}
                </td>
                <td className="py-2 pe-2">
                  <Input
                    numeric
                    inputMode="decimal"
                    aria-label={fm(wm.debitOfLine, { line: n })}
                    value={line.debit}
                    onChange={(e) => setLine(index, { debit: e.target.value, credit: "" })}
                  />
                </td>
                <td className="py-2 pe-2">
                  <Input
                    numeric
                    inputMode="decimal"
                    aria-label={fm(wm.creditOfLine, { line: n })}
                    value={line.credit}
                    onChange={(e) => setLine(index, { credit: e.target.value, debit: "" })}
                  />
                </td>
                <td className="py-2">
                  <Input
                    aria-label={fm(wm.descriptionOfLine, { line: n })}
                    value={line.description}
                    onChange={(e) => setLine(index, { description: e.target.value })}
                    onKeyDown={showContacts ? undefined : tabOut(index)}
                  />
                </td>
                {showContacts ? (
                  <td className="py-2 ps-2" data-column="contact">
                    <select
                      ref={(element) => {
                        contactRefs.current[index] = element;
                      }}
                      aria-label={fm(wm.contactOfLine, { line: n })}
                      aria-required={contactRequired(line, index) || undefined}
                      aria-invalid={(contactRequired(line, index) && !line.contact) || undefined}
                      data-required={contactRequired(line, index) ? "true" : undefined}
                      value={line.contact ?? ""}
                      onChange={(e) => setLine(index, { contact: e.target.value || null })}
                      onKeyDown={tabOut(index)}
                      className={`min-h-touch-target w-full rounded-md border bg-surface px-2 text-sm text-fg ${
                        contactRequired(line, index) && !line.contact
                          ? "border-border-danger"
                          : "border-border"
                      }`}
                    >
                      <option value="">{fm(wm.noContact)}</option>
                      {(contacts ?? []).map((contact) => (
                        <option key={contact.id} value={contact.id}>
                          {contact.display_name}
                        </option>
                      ))}
                    </select>
                    {contactRequired(line, index) && !line.contact ? (
                      <p
                        className="mt-1 text-xs font-medium text-fg-danger"
                        data-contact-required=""
                      >
                        {fm(wm.contactRequired)}
                      </p>
                    ) : null}
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            type="button"
            onClick={() => setLines((r) => [...r, emptyLine()])}
          >
            {fm(wm.addLine)}
          </Button>
          <Button
            variant="ghost"
            type="button"
            aria-pressed={showContacts}
            // Once an account needs a contact, the column stays: it can't be hidden.
            disabled={contactNeeded}
            onClick={() => setContactColumn((shown) => !shown)}
            data-toggle="contact-column"
          >
            {showContacts ? fm(wm.hideContacts) : fm(wm.showContacts)}
          </Button>
        </div>
        <div className="flex flex-col items-end gap-1">
          <p className="text-sm text-fg-muted" data-totals="">
            {fm(wm.totals, { debit: money(lines, "debit"), credit: money(lines, "credit") })}
          </p>
          <p
            role="status"
            data-difference={(off / 100).toFixed(2)}
            className={`rounded-md px-3 py-1 text-sm font-semibold ${
              off === 0 && used
                ? "bg-surface-success-subtle text-fg-success"
                : "bg-surface-warning-subtle text-fg-warning"
            }`}
          >
            {off === 0
              ? used
                ? fm(wm.balanced)
                : fm(wm.enterAmounts)
              : fm(wm.outOfBalance, {
                  amount: formatMoney((Math.abs(off) / 100).toFixed(2), { locale }),
                })}
          </p>
        </div>
      </div>

      {problems.length ? (
        <section
          aria-labelledby={`${headingId}-problems`}
          className="rounded-md border border-border-danger p-3"
        >
          <h2 id={`${headingId}-problems`} className="text-sm font-semibold text-fg-danger">
            {fm(wm.problems)}
          </h2>
          <ul className="mt-1 list-disc ps-5 text-sm text-fg">
            {problems.map((problem, i) => (
              <li key={`${problem.code}-${i}`} data-code={problem.code}>
                {problem.message}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {blocked ? (
        <p role="alert" className="text-sm font-medium text-fg-danger" data-blocked="">
          {fm(wm.blocked)}
        </p>
      ) : null}
      {failed ? (
        <p role="alert" className="text-sm text-fg-danger">
          {fm(wm.failed)}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-3">
        {needsAttachment ? (
          <Tooltip content={fm(wm.postNeedsAttachment)}>
            <span tabIndex={0} className="inline-flex rounded-md" data-post-reason="">
              <Button type="submit" disabled aria-describedby={postReasonId}>
                {fm(wm.post)}
              </Button>
              <span id={postReasonId} className="sr-only">
                {fm(wm.postNeedsAttachment)}
              </span>
            </span>
          </Tooltip>
        ) : (
          <Button type="submit" disabled={busy || !accounts || blocked || unbalanced}>
            {busy ? fm(wm.posting) : fm(wm.post)}
          </Button>
        )}
        <Button
          variant="secondary"
          type="button"
          disabled={busy || unbalanced || needsAttachment}
          onClick={() => void submit(false, "", true)}
          data-action="submit"
        >
          {fm(wm.submitForApproval)}
        </Button>
        <Button
          variant="secondary"
          type="button"
          disabled={busy}
          onClick={() => void submit(false)}
          data-action="saveDraft"
        >
          {fm(wm.saveDraft)}
        </Button>
      </div>
      <Dialog
        open={overrideOpen}
        onOpenChange={setOverrideOpen}
        title={fm(wm.overrideTitle)}
        description={fm(wm.overrideBody)}
        closeLabel={fm(wm.close)}
        footer={
          <>
            <Button variant="secondary" type="button" onClick={() => setOverrideOpen(false)}>
              {fm(wm.cancel)}
            </Button>
            <Button
              type="button"
              disabled={busy || reason.trim().length < MIN_OVERRIDE_REASON}
              onClick={() => {
                setOverrideOpen(false);
                void submit(true, reason.trim());
              }}
            >
              {fm(wm.overrideConfirm)}
            </Button>
          </>
        }
      >
        <ul className="mb-3 list-disc ps-5 text-sm text-fg-danger">
          {shortfalls.map((shortfall) => (
            <li key={shortfall.account.id}>{shortfall.message}</li>
          ))}
        </ul>
        <label htmlFor={reasonId} className="text-sm font-medium text-fg">
          {fm(wm.overrideReason, { min: MIN_OVERRIDE_REASON })}
        </label>
        <textarea
          id={reasonId}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          minLength={MIN_OVERRIDE_REASON}
          required
          className="mt-1 w-full rounded-md border border-border bg-surface p-2 text-sm text-fg"
        />
      </Dialog>
    </form>
  );
}
