"use client";

/**
 * Manual journal screen (C-03-T11…T14; per-line contact column C-03-T12),
 * `/o/:org/accounting/journals/new`: the header (date,
 * journal type, narration, automatic reversal date), the lines (account, debit, credit,
 * description) and Post / Save as draft. As the journal is typed, the server is asked what it
 * would say (`journals/check`): problems are listed before posting.
 */
import { Button, Dialog, ErrorState, Input, Tooltip } from "@numo9/ui";
import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";

import { accountsApi, type Account } from "@/accounts/api";
import { contactsApi, type ContactSummary } from "@/contacts/api";
import { useDebounced } from "@/directory/useDebounced";
import type { FileDocument } from "@/files/api";
import { uploadFile } from "@/files/upload";
import { useFormatMessage } from "@/i18n";

import {
  filledLines,
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

function money(lines: LineInput[], side: "debit" | "credit"): string {
  const cents = lines.reduce((sum, line) => sum + Math.round(Number(line[side] || 0) * 100), 0);
  return (cents / 100).toFixed(2);
}

export interface JournalFormProps {
  org: string;
  /** Where a posted or saved journal opens (default: its page). */
  navigate?: (href: string) => void;
}

export function JournalForm({ org, navigate }: Readonly<JournalFormProps>) {
  const fm = useFormatMessage();
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
    if (focusContact === null) return;
    contactRefs.current[focusContact]?.focus();
    setFocusContact(null);
  }, [focusContact, showContacts]);

  const submit = async (post: boolean, overrideReason = "") => {
    setBusy(true);
    setFailed(false);
    setRefusal(null);
    const body = overrideReason
      ? { ...input, post, override_reason: overrideReason }
      : { ...input, post };
    const result = await writeApi.create(org, body);
    setBusy(false);
    if (result.status === 201) {
      const href = `/o/${org}/accounting/journals/${result.body.id}`;
      if (navigate) navigate(href);
      else window.location.assign(href);
      return;
    }
    if (result.status === 409 && result.body.code === "ledger.journal.override_reason_required") {
      setOverrideOpen(true);
      setCheck((c) =>
        c ? { ...c, adviser: true, shortfalls: result.body.shortfalls ?? c.shortfalls } : c,
      );
      return;
    }
    if (result.status === 400 || result.status === 409) setRefusal(result.body);
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

  const shortfalls = refusal?.shortfalls ?? check?.shortfalls ?? [];
  const adviser = refusal?.adviser ?? check?.adviser ?? false;
  const blocked = shortfalls.length > 0 && !adviser;
  const flagged = lines.some(
    (line) => (accounts ?? []).find((a) => a.id === line.account)?.require_attachment,
  );
  const needsAttachment = documents.length === 0 && (Boolean(check?.needs.attachment) || flagged);

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (blocked || needsAttachment) return;
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
                  <select
                    aria-label={fm(wm.accountOfLine, { line: n })}
                    value={line.account}
                    onChange={(e) => chooseAccount(index, e.target.value)}
                    className="min-h-touch-target w-full rounded-md border border-border bg-surface px-2 text-sm text-fg"
                  >
                    <option value="">{fm(wm.chooseAccount)}</option>
                    {(accounts ?? []).map((account) => (
                      <option key={account.id} value={account.id}>
                        {fm(wm.accountOption, { code: account.code, name: account.name })}
                      </option>
                    ))}
                  </select>
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
        <p className="text-sm text-fg-muted" data-totals="">
          {fm(wm.totals, { debit: money(lines, "debit"), credit: money(lines, "credit") })}
        </p>
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
          <Button type="submit" disabled={busy || !accounts || blocked}>
            {busy ? fm(wm.posting) : fm(wm.post)}
          </Button>
        )}
        <Button
          variant="secondary"
          type="button"
          disabled={busy}
          onClick={() => void submit(false)}
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
