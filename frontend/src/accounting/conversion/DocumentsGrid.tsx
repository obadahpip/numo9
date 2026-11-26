"use client";

/**
 * Open invoices / bills grid (C-05-T12) — **paste-friendly**: paste rows copied from a
 * spreadsheet (tab-separated) into any cell and they fill the grid from that cell on, adding rows
 * as needed (a header row is skipped). Amounts and dates are read forgivingly ("$1,200.50",
 * "15/11/2025") and sent as the server expects. "Check the rows" validates every row on the
 * server without saving (dry run); "Add N documents" saves them all or none — a row's problems
 * are flagged on its cells and listed under the grid. Saved documents are listed with what was
 * still owed, and can be removed while the conversion is a draft.
 */
import {
  Button,
  formatDate,
  formatMoney,
  IconButton,
  Input,
  parseDate,
  parseMoney,
  parseTsv,
  sumDecimals,
  type AppLocale,
} from "@numo9/ui";
import { CloseIcon } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useState, type ClipboardEvent } from "react";

import { useFormatMessage } from "@/i18n";

import {
  conversionApi,
  type DocumentInput,
  type DocumentKind,
  type OpeningDocument,
  type RowResult,
} from "./api";
import { dm } from "./documentMessages";

export const COLUMNS = [
  "contact",
  "number",
  "date",
  "due_date",
  "total",
  "outstanding",
  "reference",
] as const;
export type Column = (typeof COLUMNS)[number];
export type DraftRow = { key: string } & Record<Column, string>;

let seq = 0;
export function emptyRow(): DraftRow {
  seq += 1;
  return {
    key: `doc-${seq}`,
    contact: "",
    number: "",
    date: "",
    due_date: "",
    total: "",
    outstanding: "",
    reference: "",
  };
}

const filled = (row: DraftRow) => COLUMNS.some((c) => row[c].trim() !== "");

/** A pasted first row that is a header ("Customer  Number  Date  …"): no amount, no date. */
function isHeader(cells: string[], columns: readonly Column[], locale: AppLocale): boolean {
  const at = (name: Column) => cells[columns.indexOf(name)] ?? "";
  const total = at("total").trim();
  const date = at("date").trim();
  return (
    (total !== "" || date !== "") &&
    (total === "" || parseMoney(total, { locale }) === null) &&
    (date === "" || parseDate(date, { today: "2026-01-01", locale }) === null)
  );
}

/** Fill `rows` from `cells` (rows × cells) at row `start`, column `from` on. */
export function pasteInto(
  rows: readonly DraftRow[],
  cells: string[][],
  start: number,
  from: Column,
  locale: AppLocale,
): { rows: DraftRow[]; count: number } {
  const columns = COLUMNS.slice(COLUMNS.indexOf(from));
  const data =
    cells.length > 1 && isHeader(cells[0] ?? [], columns, locale) ? cells.slice(1) : cells;
  const next = [...rows];
  data.forEach((values, offset) => {
    const at = start + offset;
    const row = { ...(next[at] ?? emptyRow()) };
    columns.forEach((column, i) => {
      const value = values[i];
      if (value !== undefined) row[column] = value.trim();
    });
    next[at] = row;
  });
  return { rows: next, count: data.length };
}

function toInput(
  row: DraftRow,
  kind: DocumentKind,
  locale: AppLocale,
  today: string,
): DocumentInput {
  const money = (text: string) => (text.trim() ? (parseMoney(text, { locale }) ?? text) : "");
  const day = (text: string) => (text.trim() ? (parseDate(text, { today, locale }) ?? text) : "");
  const input: DocumentInput = {
    contact: row.contact,
    date: day(row.date),
    total: money(row.total),
    reference: row.reference,
  };
  if (kind === "invoice") input.number = row.number;
  else input.supplier_invoice_no = row.number;
  const due = day(row.due_date);
  if (due) input.due_date = due;
  const owed = money(row.outstanding);
  if (owed) input.outstanding = owed;
  return input;
}

/** The server's field → the grid's column. */
const FIELD_COLUMN: Record<string, Column> = {
  contact: "contact",
  number: "number",
  supplier_invoice_no: "number",
  date: "date",
  due_date: "due_date",
  total: "total",
  outstanding: "outstanding",
  reference: "reference",
};

export interface DocumentsGridProps {
  org: string;
  kind: DocumentKind;
  documents: readonly OpeningDocument[];
  readOnly: boolean;
  /** Called after documents were added or removed (the wizard reloads them and the meter). */
  onChanged: () => void;
  /** "Today" for reading short dates (tests). */
  today?: string;
}

export function DocumentsGrid({
  org,
  kind,
  documents,
  readOnly,
  onChanged,
  today = new Date().toISOString().slice(0, 10),
}: DocumentsGridProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [rows, setRows] = useState<DraftRow[]>(() => [emptyRow()]);
  const [results, setResults] = useState<RowResult[]>([]);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const headers: Record<Column, string> = {
    contact: fm(dm.contact, { kind }),
    number: fm(dm.number, { kind }),
    date: fm(dm.date),
    due_date: fm(dm.dueDate),
    total: fm(dm.total),
    outstanding: fm(dm.outstanding),
    reference: fm(dm.reference),
  };
  const ready = rows.filter(filled);
  const problemsOf = (index: number) => results.find((r) => r.row === index + 1)?.errors ?? [];

  const set = (index: number, column: Column, value: string) =>
    setRows((all) => all.map((row, i) => (i === index ? { ...row, [column]: value } : row)));

  const onPaste = (event: ClipboardEvent<HTMLInputElement>, index: number, column: Column) => {
    const text = event.clipboardData.getData("text/plain");
    if (!/[\t\n]/.test(text.replace(/\r?\n$/, ""))) return; // one value: the browser pastes it
    event.preventDefault();
    const cells = parseTsv(text);
    const pasted = pasteInto(rows, cells, index, column, locale);
    setRows(pasted.rows);
    setMessage(fm(dm.pasted, { count: pasted.count }));
    setFailed(false);
    setResults([]);
  };

  const send = async (dryRun: boolean) => {
    const batch = rows.filter(filled);
    if (!batch.length) return;
    setBusy(true);
    setFailed(false);
    setMessage("");
    const answer = await conversionApi
      .addDocuments(
        org,
        kind,
        batch.map((row) => toInput(row, kind, locale, today)),
        dryRun,
      )
      .catch(() => null);
    setBusy(false);
    const body = answer?.body;
    if (!answer || !body || !Array.isArray(body.rows)) {
      setFailed(true);
      setMessage(body?.detail || fm(dm.failed));
      return;
    }
    setRows(batch.length ? batch : [emptyRow()]);
    setResults(body.rows as RowResult[]);
    if (body.errors) {
      setFailed(true);
      setMessage(fm(dm.invalid, { count: body.errors }));
    } else if (dryRun) {
      setMessage(fm(dm.valid, { count: body.ok }));
    } else {
      setMessage(fm(dm.added, { count: body.written }));
      setRows([emptyRow()]);
      setResults([]);
      onChanged();
    }
  };

  const remove = async (id: string) => {
    setBusy(true);
    const answer = await conversionApi.removeDocuments(org, [id]).catch(() => null);
    setBusy(false);
    if (answer?.status === 200) onChanged();
    else {
      setFailed(true);
      setMessage(answer?.body.detail || fm(dm.failed));
    }
  };

  const owed = sumDecimals(documents.map((d) => d.outstanding));
  const money = (value: string) => formatMoney(value, { locale, currency: "CAD" });

  return (
    <div className="flex flex-col gap-4" data-documents={kind}>
      <p className="max-w-3xl text-sm text-fg-muted">
        {fm(kind === "invoice" ? dm.invoicesIntro : dm.billsIntro)}
      </p>

      {readOnly ? null : (
        <div className="flex flex-col gap-2">
          <table className="w-full text-sm" aria-label={fm(dm.grid, { kind })} data-grid={kind}>
            <thead>
              <tr className="text-xs text-fg-muted">
                {COLUMNS.map((column) => (
                  <th key={column} scope="col" className="py-1 text-start">
                    {headers[column]}
                  </th>
                ))}
                <th scope="col" className="w-10">
                  <span className="sr-only">{fm(dm.removeRow, { row: "" })}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => {
                const problems = problemsOf(index);
                const bad = new Set(problems.map((p) => FIELD_COLUMN[p.field] ?? "contact"));
                return (
                  <tr
                    key={row.key}
                    data-row={index + 1}
                    data-invalid={problems.length ? "" : undefined}
                    className="border-t border-border align-top"
                  >
                    {COLUMNS.map((column) => (
                      <td
                        key={column}
                        className="py-1 pe-1"
                        data-invalid={bad.has(column) || undefined}
                      >
                        <Input
                          aria-label={fm(dm.cell, { column: headers[column], row: index + 1 })}
                          aria-invalid={bad.has(column) || undefined}
                          value={row[column]}
                          numeric={column === "total" || column === "outstanding"}
                          inputMode={
                            column === "total" || column === "outstanding" ? "decimal" : undefined
                          }
                          onChange={(e) => set(index, column, e.target.value)}
                          onPaste={(e) => onPaste(e, index, column)}
                        />
                      </td>
                    ))}
                    <td className="py-1">
                      <IconButton
                        label={fm(dm.removeRow, { row: index + 1 })}
                        icon={<CloseIcon />}
                        variant="ghost"
                        onClick={() =>
                          setRows((all) =>
                            all.length > 1 ? all.filter((_, i) => i !== index) : [emptyRow()],
                          )
                        }
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <ul className="text-xs text-fg-danger" data-problems="">
            {results.flatMap((result) =>
              result.errors.map((problem) => (
                <li key={`${result.row}-${problem.field}-${problem.code}`}>
                  {fm(dm.rowProblem, { row: result.row, message: problem.message })}
                </li>
              )),
            )}
          </ul>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setRows((all) => [...all, emptyRow()])}>
              {fm(dm.addRow)}
            </Button>
            <Button variant="secondary" disabled={busy || !ready.length} onClick={() => send(true)}>
              {fm(dm.check)}
            </Button>
            <Button variant="primary" disabled={busy || !ready.length} onClick={() => send(false)}>
              {fm(dm.add, { count: ready.length })}
            </Button>
          </div>
          <p
            aria-live="polite"
            className={failed ? "text-sm text-fg-danger" : "text-sm text-fg-success"}
            data-result=""
          >
            {message}
          </p>
        </div>
      )}

      <table className="w-full text-sm" data-saved={kind}>
        <caption className="pb-1 text-start font-semibold text-fg">
          {fm(dm.saved, { kind })}
        </caption>
        <thead>
          <tr className="text-xs text-fg-muted">
            <th scope="col" className="py-1 text-start">
              {headers.contact}
            </th>
            <th scope="col" className="py-1 text-start">
              {headers.number}
            </th>
            <th scope="col" className="py-1 text-start">
              {headers.date}
            </th>
            <th scope="col" className="py-1 text-end">
              {headers.total}
            </th>
            <th scope="col" className="py-1 text-end">
              {headers.outstanding}
            </th>
            <th scope="col" className="w-24">
              <span className="sr-only">{fm(dm.remove)}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {documents.length === 0 ? (
            <tr>
              <td colSpan={6} className="py-2 text-fg-muted">
                {fm(dm.none)}
              </td>
            </tr>
          ) : (
            documents.map((doc) => {
              const number = kind === "invoice" ? doc.number : doc.supplier_invoice_no;
              return (
                <tr key={doc.id} className="border-t border-border" data-document={doc.id}>
                  <td className="py-1">{doc.contact?.name}</td>
                  <td className="py-1">{number}</td>
                  <td className="py-1">{formatDate(doc.date, { locale })}</td>
                  <td className="py-1 text-end tabular-nums">{money(doc.total)}</td>
                  <td className="py-1 text-end tabular-nums">{money(doc.outstanding)}</td>
                  <td className="py-1 text-end">
                    {readOnly ? null : (
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={busy}
                        aria-label={fm(dm.removeNamed, { number })}
                        onClick={() => remove(doc.id)}
                      >
                        {fm(dm.remove)}
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={6} className="pt-2 text-xs text-fg-muted" data-owed={owed}>
              {fm(dm.totalOwed, { count: documents.length, amount: money(owed) })}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
