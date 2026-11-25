"use client";

/**
 * Find & recode — new coding, preview and confirm (C-07-T12).
 *
 * - `ChangesForm`: the new account, tax code (or none), tracking option and contact (or none);
 *   a field left empty keeps its value;
 * - `RecodePreviewPanel`: the summary ("2 lines change · totals unchanged"), the totals of each
 *   book, the tax impact when a tax code changes, and the **diff** — before / after per line,
 *   each changed value marked;
 * - `ConfirmRecode`: the dialog with the numbers (lines, entries reversed and re-posted, debits
 *   and credits that stay the same, excluded lines) and, when the tax changes, a required
 *   acknowledgement.
 */
import {
  Button,
  Checkbox,
  Dialog,
  formatDate,
  formatMoney,
  INPUT_BASE,
  type AppLocale,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useState } from "react";

import { useFormatMessage } from "@/i18n";

import type { Changes, Coding, PreviewLine, PreviewResult } from "./api";
import type { AccountOption } from "./ConditionBuilder";
import { rm } from "./messages";

const control = `${INPUT_BASE} border-border`;

export interface ChangesDraft {
  account: string;
  taxCode: string;
  clearTax: boolean;
  category: string;
  option: string;
  contact: string;
  clearContact: boolean;
}

export const EMPTY_CHANGES: ChangesDraft = {
  account: "",
  taxCode: "",
  clearTax: false,
  category: "",
  option: "",
  contact: "",
  clearContact: false,
};

/** The draft as the API's `changes`; `null` when nothing would change. */
export function toChanges(draft: ChangesDraft): Changes | null {
  const out: Changes = {};
  if (draft.account) out.account = draft.account;
  if (draft.clearTax) out.tax_code = "";
  else if (draft.taxCode.trim()) out.tax_code = draft.taxCode.trim();
  if (draft.category.trim() && draft.option.trim()) {
    out.tracking = { [draft.category.trim()]: draft.option.trim() };
  }
  if (draft.clearContact) out.contact = null;
  else if (draft.contact.trim()) out.contact = draft.contact.trim();
  return Object.keys(out).length ? out : null;
}

export function ChangesForm({
  draft,
  accounts,
  onChange,
}: {
  draft: ChangesDraft;
  accounts: AccountOption[];
  onChange: (draft: ChangesDraft) => void;
}) {
  const fm = useFormatMessage();
  const set = (patch: Partial<ChangesDraft>) => onChange({ ...draft, ...patch });
  return (
    <fieldset className="flex flex-col gap-3" data-recode-changes="">
      <legend className="text-base font-semibold text-fg">{fm(rm.newCoding)}</legend>
      <p className="text-sm text-fg-muted">{fm(rm.newCodingHint)}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-fg">
          {fm(rm.newAccount)}
          <select
            className={control}
            value={draft.account}
            onChange={(event) => set({ account: event.target.value })}
          >
            <option value="">{fm(rm.keepAccount)}</option>
            {accounts.map((account) => (
              <option key={account.id} value={account.id}>
                {account.label}
              </option>
            ))}
          </select>
        </label>
        <div className="flex flex-col gap-1 text-sm text-fg">
          <label className="flex flex-col gap-1">
            {fm(rm.newTaxCode)}
            <input
              className={control}
              value={draft.taxCode}
              disabled={draft.clearTax}
              onChange={(event) => set({ taxCode: event.target.value })}
            />
          </label>
          <Checkbox
            label={fm(rm.clearTax)}
            checked={draft.clearTax}
            onCheckedChange={(on) => set({ clearTax: on === true })}
          />
        </div>
        <div className="flex flex-col gap-1 text-sm text-fg">
          <span>{fm(rm.newTracking)}</span>
          <div className="flex gap-2">
            <label className="flex flex-1 flex-col gap-1 text-xs text-fg-muted">
              {fm(rm.category)}
              <input
                className={control}
                value={draft.category}
                onChange={(event) => set({ category: event.target.value })}
              />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-xs text-fg-muted">
              {fm(rm.option)}
              <input
                className={control}
                value={draft.option}
                onChange={(event) => set({ option: event.target.value })}
              />
            </label>
          </div>
        </div>
        <div className="flex flex-col gap-1 text-sm text-fg">
          <label className="flex flex-col gap-1">
            {fm(rm.newContact)}
            <input
              className={control}
              value={draft.contact}
              disabled={draft.clearContact}
              onChange={(event) => set({ contact: event.target.value })}
            />
          </label>
          <Checkbox
            label={fm(rm.clearContact)}
            checked={draft.clearContact}
            onCheckedChange={(on) => set({ clearContact: on === true })}
          />
        </div>
      </div>
    </fieldset>
  );
}

const FIELDS = ["account", "tax_code", "tracking", "contact"] as const;

function tracking(value: Record<string, string>) {
  return Object.entries(value)
    .map(([k, v]) => `${k}: ${v}`)
    .join("; ");
}

export function RecodePreviewPanel({
  preview,
  accounts,
}: {
  preview: PreviewResult;
  accounts: AccountOption[];
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const names = new Map(accounts.map((a) => [a.id, a.label]));
  const none = fm(rm.none);
  const show = (coding: Coding, field: (typeof FIELDS)[number]) => {
    if (field === "account") return names.get(coding.account) ?? coding.account;
    if (field === "tax_code") return coding.tax_code || none;
    if (field === "tracking") return tracking(coding.tracking) || none;
    return coding.contact ?? none;
  };
  const columns = {
    account: fm(rm.colAccount),
    tax_code: fm(rm.colTax),
    tracking: fm(rm.colTracking),
    contact: fm(rm.colContact),
  };
  const money = (value: string) => (Number(value) ? formatMoney(value, { locale }) : "");
  const summary = preview.summary;

  return (
    <section className="flex flex-col gap-3" data-recode-preview="">
      <h2 className="text-base font-semibold text-fg">{fm(rm.preview)}</h2>
      <p className="text-sm font-medium text-fg" data-preview-summary="">
        {fm(rm.previewSummary, {
          lines: summary.lines,
          unchanged: summary.unchanged,
          totals: summary.totals_unchanged ? "yes" : "no",
        })}
      </p>
      <ul className="text-sm text-fg-muted">
        {Object.entries(preview.totals_after).map(([book, totals]) => (
          <li key={book}>
            {fm(rm.booksTotals, {
              book: fm(rm.bookName, { book }),
              debit: formatMoney(totals.debit, { locale }),
              credit: formatMoney(totals.credit, { locale }),
            })}
          </li>
        ))}
      </ul>
      {summary.needs_confirmation ? (
        <p role="alert" className="text-sm text-fg-warning" data-tax-impact="">
          {fm(rm.taxImpact, { delta: formatMoney(summary.tax_delta, { locale }) })}
        </p>
      ) : null}
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-diff="">
          <thead>
            <tr className="text-left text-xs text-fg-muted">
              <th scope="col" className="p-1">
                {fm(rm.colJournal)}
              </th>
              <th scope="col" className="p-1">
                {fm(rm.colDate)}
              </th>
              <th scope="col" className="p-1 text-end">
                {fm(rm.colDebit)}
              </th>
              <th scope="col" className="p-1 text-end">
                {fm(rm.colCredit)}
              </th>
              {FIELDS.map((field) => (
                <th key={field} scope="col" className="p-1">
                  {columns[field]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.lines.map((row: PreviewLine) => (
              <tr
                key={`${row.entry}:${row.line_no}`}
                className="border-t border-border align-top"
                data-diff-line={`${row.entry}:${row.line_no}`}
              >
                <td className="p-1 font-medium whitespace-nowrap">
                  {fm(rm.journalLine, { number: row.number, line: row.line_no })}
                </td>
                <td className="p-1 whitespace-nowrap">{formatDate(row.date, { locale })}</td>
                <td className="p-1 text-end tabular-nums">{money(row.debit)}</td>
                <td className="p-1 text-end tabular-nums">{money(row.credit)}</td>
                {FIELDS.map((field) => {
                  const changed = row.changed.includes(field);
                  return (
                    <td key={field} className="p-1" data-field={field}>
                      {changed ? (
                        <span className="sr-only">
                          {fm(rm.changedField, {
                            field: columns[field],
                            before: show(row.before, field),
                            after: show(row.after, field),
                          })}
                        </span>
                      ) : null}
                      <span
                        aria-hidden={changed ? true : undefined}
                        className={changed ? "text-fg-muted line-through" : ""}
                      >
                        {show(row.before, field)}
                      </span>
                      {changed ? (
                        <span aria-hidden className="block font-semibold text-fg" data-after="">
                          {show(row.after, field)}
                        </span>
                      ) : null}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function ConfirmRecode({
  open,
  onOpenChange,
  preview,
  busy,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  preview: PreviewResult;
  busy: boolean;
  onConfirm: () => void;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [taxOk, setTaxOk] = useState(false);
  const summary = preview.summary;
  const accounting = preview.totals_after.accounting ?? { debit: "0", credit: "0" };
  const delta = formatMoney(summary.tax_delta, { locale });
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setTaxOk(false);
        onOpenChange(next);
      }}
      title={fm(rm.confirmTitle, { count: summary.lines })}
      closeLabel={fm(rm.close)}
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            {fm(rm.cancel)}
          </Button>
          <Button
            variant="primary"
            disabled={busy || (summary.needs_confirmation && !taxOk)}
            onClick={onConfirm}
          >
            {fm(rm.confirm)}
          </Button>
        </>
      }
    >
      <p className="text-sm text-fg" data-confirm-numbers="">
        {fm(rm.confirmBody, {
          entries: summary.entries,
          debit: formatMoney(accounting.debit, { locale }),
          credit: formatMoney(accounting.credit, { locale }),
          excluded: summary.excluded,
        })}
      </p>
      {summary.needs_confirmation ? (
        <div className="mt-3">
          <Checkbox
            label={fm(rm.confirmTax, { delta })}
            checked={taxOk}
            onCheckedChange={(on) => setTaxOk(on === true)}
          />
        </div>
      ) : null}
    </Dialog>
  );
}
