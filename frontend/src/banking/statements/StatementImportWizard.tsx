"use client";

/**
 * Statement import wizard (F-02-T12): Upload → Map → Preview → Confirm, with a progress stepper.
 *
 * 1. **Upload** — drag-and-drop zone (or "Choose a file"), the formats accepted and where to find
 *    them. The server reads the file and says what it found: the format, encoding and delimiter,
 *    the number of lines, and for CSV / XLSX the saved mapping it recognised (the account's own
 *    first, F-02-T06). OFX / QFX / QBO files skip the Map step.
 * 2. **Map** — the first 5 rows of the file with a dropdown per column (date, description, payee,
 *    reference, amount, withdrawal, deposit, running balance…), the date format (ambiguous dates
 *    are flagged, never guessed), the sign convention, decimal separator, header and rows to skip.
 * 3. **Preview** — a dry run: tabs New / Duplicates / Errors with their counts, each line with its
 *    reason (row + fix), the statement's closing balance, and "Skip errors and import valid
 *    lines".
 * 4. **Confirm** — what will be imported and skipped; Import. The result toast offers "Undo
 *    import"; files of more than 2,000 lines are imported by a background job (job tray).
 */
import {
  Button,
  Checkbox,
  Input,
  Switch,
  Tabs,
  ToastProvider,
  formatDate,
  formatMoney,
  useOptionalToast,
  type AppLocale,
} from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useId, useRef, useState, type DragEvent, type ReactNode } from "react";

import { useFormatMessage } from "@/i18n";

import { bankingApi, type BankAccount } from "../api";
import {
  gridRows,
  importsApi,
  layoutComplete,
  padColumns,
  refusalText,
  type Layout,
  type LineStatus,
  type Preview,
  type PreviewLine,
  type Role,
  type Sign,
  type Upload,
} from "./api";
import { imp, roleLabels, signLabels, statusLabels } from "./messages";

type Step = 1 | 2 | 3 | 4;
const ROLES: Role[] = [
  "ignore",
  "date",
  "description",
  "payee",
  "reference",
  "amount",
  "debit",
  "credit",
  "balance",
  "fitid",
];
const SIGNS: Sign[] = ["signed", "inverted", "debit_credit"];
const STATUSES: LineStatus[] = ["new", "duplicate", "error"];
const TIME_ZONE = "America/Toronto";
const ACCEPT = ".csv,.xlsx,.ofx,.qfx,.qbo";
const ENCODINGS: Record<string, string> = {
  "utf-8": "UTF-8",
  "utf-8-sig": "UTF-8 (BOM)",
  "utf-16": "UTF-16",
  cp1252: "Windows-1252",
  latin_1: "ISO-8859-1",
  iso8859_15: "ISO-8859-15",
  mac_roman: "Mac Roman",
};

/** The wizard in its page: toasts (the result and its Undo) live in their own region. */
export function StatementImportScreen({ org, account }: { org: string; account: string }) {
  const fm = useFormatMessage();
  return (
    <ToastProvider labels={{ region: fm(imp.toastRegion, { hotkey: "F8" }), close: fm(imp.close) }}>
      <StatementImportWizard org={org} account={account} />
    </ToastProvider>
  );
}

export function StatementImportWizard({
  org,
  account: accountId,
}: {
  org: string;
  account: string;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const toasts = useOptionalToast();
  const ids = useId();
  const picker = useRef<HTMLInputElement>(null);
  const [account, setAccount] = useState<BankAccount | null>(null);
  const [step, setStep] = useState<Step>(1);
  const [upload, setUpload] = useState<Upload | null>(null);
  const [layout, setLayout] = useState<Layout | null>(null);
  const [mapping, setMapping] = useState<string | null>(null);
  const [edited, setEdited] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [tab, setTab] = useState<LineStatus>("new");
  const [skipErrors, setSkipErrors] = useState(false);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [finished, setFinished] = useState<"done" | "background" | null>(null);

  useEffect(() => {
    void bankingApi.account(org, accountId).then((result) => {
      if (result.status === 200) setAccount(result.body);
    });
  }, [org, accountId]);

  const currency = account?.currency ?? "CAD";
  const names = [fm(imp.stepUpload), fm(imp.stepMap), fm(imp.stepPreview), fm(imp.stepConfirm)];
  const importId = upload?.import.id ?? "";

  const choice = () => ({
    mapping: mapping,
    layout: upload?.tabular ? layout : null,
  });

  const runPreview = async (current: Upload, chosen: Layout | null, saved: string | null) => {
    setBusy(true);
    setError("");
    const result = await importsApi.preview(org, accountId, current.import.id, {
      mapping: saved,
      layout: current.tabular ? chosen : null,
      limit: 1000,
    });
    setBusy(false);
    if (result.status === 200) {
      setPreview(result.body);
      setTab(result.body.counts.error && !result.body.counts.new ? "error" : "new");
      setStep(3);
    } else {
      setError(fm(imp.previewFailed, { reason: refusalText(result.body) ?? "" }));
    }
  };

  const send = async (file: File) => {
    setBusy(true);
    setError("");
    setFinished(null);
    const result = await importsApi.upload(org, accountId, file);
    setBusy(false);
    if (result.status !== 201) {
      setError(fm(imp.uploadFailed, { reason: refusalText(result.body) ?? file.name }));
      return;
    }
    const body = result.body;
    setUpload(body);
    setPreview(null);
    setSkipErrors(false);
    setEdited(false);
    setMapping(body.mapping?.id ?? null);
    if (body.tabular && body.layout) {
      const padded = {
        ...body.layout,
        columns: padColumns(body.layout.columns, body.sample?.width ?? 0),
      };
      setLayout(padded);
      setStep(2);
    } else {
      setLayout(null);
      await runPreview(body, null, null);
    }
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) void send(file);
  };

  const change = (next: Partial<Layout>) => {
    if (!layout) return;
    setLayout({ ...layout, ...next });
    setEdited(true);
  };

  const pickMapping = (value: string) => {
    const saved = upload?.mappings?.find((item) => item.id === value);
    if (!saved || !upload) return;
    setMapping(saved.id);
    setEdited(false);
    setLayout({
      ...saved.layout,
      columns: padColumns(saved.layout.columns, upload.sample?.width ?? 0),
    });
  };

  const commit = async () => {
    if (!upload) return;
    setBusy(true);
    setError("");
    const result = await importsApi.commit(org, accountId, importId, {
      ...choice(),
      skip_errors: skipErrors,
    });
    setBusy(false);
    if (result.status === 202) {
      setFinished("background");
      return;
    }
    if (result.status !== 200) {
      setError(fm(imp.commitFailed, { reason: refusalText(result.body) ?? "" }));
      return;
    }
    setFinished("done");
    const done = result.body.import;
    toasts?.toast({
      title: fm(imp.done, { count: done.counts.new, file: done.file_name }),
      tone: "success",
      undo: {
        label: fm(imp.undo),
        altText: fm(imp.undoAlt),
        onUndo: () => {
          void importsApi.undo(org, accountId, done.id).then((undone) => {
            toasts?.toast(
              undone.status === 200
                ? { title: fm(imp.undone) }
                : {
                    title: fm(imp.undoFailed, { reason: refusalText(undone.body) ?? "" }),
                    tone: "danger",
                  },
            );
          });
        },
      },
    });
  };

  const money = (value: string | null) =>
    value === null ? "" : formatMoney(value, { locale, currency });
  const day = (value: string | null) =>
    value ? formatDate(value, { locale, timeZone: TIME_ZONE }) : "";

  const detection = upload ? detectionText(upload, fm) : "";
  const counts = preview?.counts;
  const blocked = Boolean(counts && counts.error > 0 && !skipErrors);
  const grid = upload?.sample && layout ? gridRows(upload.sample.rows, layout) : null;

  return (
    <div className="flex max-w-5xl flex-col gap-6" data-statement-import="">
      <nav aria-label={fm(imp.back)} className="text-sm">
        <Link href={`/o/${org}/banking/${accountId}`} className="underline">
          {fm(imp.back)}
        </Link>
      </nav>
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-fg">{fm(imp.title)}</h1>
        {account ? <p className="text-sm font-semibold text-fg">{account.display_name}</p> : null}
        <p className="text-sm text-fg-muted">{fm(imp.intro)}</p>
      </header>
      <ol aria-label={fm(imp.steps)} className="flex flex-wrap gap-2 text-sm" data-stepper="">
        {names.map((name, index) => {
          const n = (index + 1) as Step;
          const skipped = n === 2 && upload !== null && !upload.tabular;
          return (
            <li
              key={name}
              aria-current={step === n ? "step" : undefined}
              className={[
                "rounded-full border px-3 py-1",
                step === n ? "border-fg font-semibold text-fg" : "border-border text-fg-muted",
                skipped ? "line-through" : "",
              ].join(" ")}
            >
              {fm(imp.stepItem, { n, name })}
            </li>
          );
        })}
      </ol>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger" data-import-error="">
          {error}
        </p>
      ) : null}
      {detection ? (
        <p role="status" className="text-sm text-fg" data-detection="">
          {detection}
        </p>
      ) : null}
      {upload?.warnings.map((warning) => (
        <p key={warning} className="text-sm text-fg-warning">
          {warning}
        </p>
      ))}

      {step === 1 ? (
        <section aria-labelledby={`${ids}-upload`} className="flex flex-col gap-4">
          <h2 id={`${ids}-upload`} className="sr-only">
            {fm(imp.stepUpload)}
          </h2>
          <div
            data-dropzone=""
            data-dragging={dragging ? "" : undefined}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={[
              "flex flex-col items-center gap-3 rounded-lg border-2 border-dashed p-10 text-center",
              dragging ? "border-fg bg-surface-accent" : "border-border",
            ].join(" ")}
          >
            <p className="text-base font-semibold text-fg">{fm(imp.dropTitle)}</p>
            <Button variant="secondary" disabled={busy} onClick={() => picker.current?.click()}>
              {fm(imp.chooseFile)}
            </Button>
            <input
              ref={picker}
              type="file"
              accept={ACCEPT}
              aria-label={fm(imp.chooseFile)}
              className="sr-only"
              tabIndex={-1}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void send(file);
                event.target.value = "";
              }}
            />
            <p className="text-xs text-fg-muted">{fm(imp.dropHelp)}</p>
            {busy ? <p className="text-sm text-fg-muted">{fm(imp.uploading)}</p> : null}
          </div>
          <div className="text-sm text-fg-muted" data-format-help="">
            <h3 className="font-semibold text-fg">{fm(imp.formatsTitle)}</h3>
            <ul className="list-disc ps-5">
              <li>{fm(imp.formatsCsv)}</li>
              <li>{fm(imp.formatsOfx)}</li>
            </ul>
          </div>
        </section>
      ) : null}

      {step === 2 && upload && layout && grid ? (
        <section aria-labelledby={`${ids}-map`} className="flex flex-col gap-4">
          <h2 id={`${ids}-map`} className="text-lg font-semibold">
            {fm(imp.stepMap)}
          </h2>
          <p className="text-sm" data-mapping-detected="">
            {upload.mapping && !edited
              ? fm(imp.mappingDetected, { name: upload.mapping.name })
              : upload.mapping
                ? null
                : fm(imp.mappingNone)}
          </p>
          {upload.date_ambiguous ? (
            <p className="text-sm text-fg-warning" data-date-ambiguous="">
              {fm(imp.dateAmbiguous, { formats: (upload.date_formats ?? []).join(" / ") })}
            </p>
          ) : null}
          <div className="flex flex-wrap items-end gap-4">
            <Control id={`${ids}-mapping`} label={fm(imp.savedMapping)}>
              <select
                id={`${ids}-mapping`}
                value={edited ? "" : (mapping ?? "")}
                onChange={(event) => pickMapping(event.target.value)}
                className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-fg"
              >
                {edited || !mapping ? <option value="">{fm(imp.customMapping)}</option> : null}
                {(upload.mappings ?? []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </Control>
            <Control id={`${ids}-date`} label={fm(imp.dateFormat)}>
              <select
                id={`${ids}-date`}
                value={layout.date_format}
                onChange={(event) => change({ date_format: event.target.value })}
                className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-fg"
              >
                {(upload.choices?.date_formats ?? [layout.date_format]).map((format) => (
                  <option key={format} value={format}>
                    {format}
                  </option>
                ))}
              </select>
            </Control>
            <Control id={`${ids}-sign`} label={fm(imp.sign)}>
              <select
                id={`${ids}-sign`}
                value={layout.sign}
                onChange={(event) => change({ sign: event.target.value as Sign })}
                className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-fg"
              >
                {SIGNS.map((sign) => (
                  <option key={sign} value={sign}>
                    {fm(signLabels[sign])}
                  </option>
                ))}
              </select>
            </Control>
            <Control id={`${ids}-decimal`} label={fm(imp.decimal)}>
              <select
                id={`${ids}-decimal`}
                value={layout.decimal_separator}
                onChange={(event) =>
                  change({ decimal_separator: event.target.value === "," ? "," : "." })
                }
                className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-fg"
              >
                <option value=".">{fm(imp.decimalDot)}</option>
                <option value=",">{fm(imp.decimalComma)}</option>
              </select>
            </Control>
            <Control id={`${ids}-skip`} label={fm(imp.skipRows)}>
              <Input
                id={`${ids}-skip`}
                type="number"
                min={0}
                max={20}
                value={String(layout.skip_rows)}
                onChange={(event) =>
                  change({ skip_rows: Math.max(0, Number(event.target.value) || 0) })
                }
                className="w-24"
              />
            </Control>
            <Checkbox
              label={fm(imp.hasHeader)}
              checked={layout.has_header}
              onCheckedChange={(value) => change({ has_header: value === true })}
            />
          </div>
          <div className="overflow-x-auto rounded-md border border-border">
            <table aria-label={fm(imp.grid)} className="min-w-full text-sm" data-mapping-grid="">
              <thead>
                <tr>
                  {layout.columns.map((role, index) => (
                    <th key={index} scope="col" className="p-2 text-start align-top font-normal">
                      <select
                        aria-label={fm(imp.columnRole, { n: index + 1 })}
                        value={role}
                        onChange={(event) => {
                          const columns = [...layout.columns];
                          columns[index] = event.target.value as Role;
                          change({ columns });
                        }}
                        className="h-9 w-full min-w-32 rounded-md border border-border bg-surface px-2 text-sm text-fg"
                      >
                        {ROLES.map((option) => (
                          <option key={option} value={option}>
                            {fm(roleLabels[option])}
                          </option>
                        ))}
                      </select>
                      {grid.header ? (
                        <span className="mt-1 block text-xs font-semibold text-fg-muted">
                          {grid.header.cells[index] ?? ""}
                        </span>
                      ) : null}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {grid.data.map((row) => (
                  <tr key={row.row} className="border-t border-border">
                    {layout.columns.map((role, index) => (
                      <td
                        key={index}
                        className={role === "ignore" ? "p-2 text-fg-muted" : "p-2 text-fg"}
                      >
                        {row.cells[index] ?? ""}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!layoutComplete(layout) ? (
            <p className="text-sm text-fg-danger">{fm(imp.mapIncomplete)}</p>
          ) : null}
          <div className="flex gap-3">
            <Button variant="ghost" onClick={() => setStep(1)}>
              {fm(imp.previous)}
            </Button>
            <Button
              variant="primary"
              disabled={busy || !layoutComplete(layout)}
              onClick={() => void runPreview(upload, layout, mapping)}
            >
              {fm(imp.toPreview)}
            </Button>
          </div>
        </section>
      ) : null}

      {step === 3 && preview && counts ? (
        <section aria-labelledby={`${ids}-preview`} className="flex flex-col gap-4">
          <h2 id={`${ids}-preview`} className="text-lg font-semibold">
            {fm(imp.stepPreview)}
          </h2>
          {preview.balances.closing ? (
            <p className="text-sm" data-closing-balance="">
              {fm(imp.closing, {
                amount: money(preview.balances.closing.amount),
                date: day(preview.balances.closing.date),
              })}
            </p>
          ) : null}
          <Tabs
            label={fm(imp.tabs)}
            value={tab}
            onValueChange={(value) => setTab(value as LineStatus)}
            items={STATUSES.map((status) => ({
              value: status,
              label: fm(statusLabels[status]),
              count: counts[status],
              content: (
                <LinesTable
                  lines={preview.results.filter((line) => line.status === status)}
                  total={counts[status]}
                  money={money}
                  day={day}
                />
              ),
            }))}
          />
          {counts.error > 0 ? (
            <Switch
              label={fm(imp.skipErrors)}
              checked={skipErrors}
              onCheckedChange={setSkipErrors}
            />
          ) : null}
          <div className="flex gap-3">
            <Button variant="ghost" onClick={() => setStep(upload?.tabular ? 2 : 1)}>
              {fm(imp.previous)}
            </Button>
            <Button variant="primary" onClick={() => setStep(4)}>
              {fm(imp.next)}
            </Button>
          </div>
        </section>
      ) : null}

      {step === 4 && counts ? (
        <section aria-labelledby={`${ids}-confirm`} className="flex flex-col gap-4">
          <h2 id={`${ids}-confirm`} className="text-lg font-semibold">
            {fm(imp.stepConfirm)}
          </h2>
          {finished === "background" ? (
            <p role="status" data-import-background="">
              {fm(imp.background)}
            </p>
          ) : finished === "done" ? null : (
            <ul className="flex flex-col gap-1 text-sm" data-confirm-summary="">
              <li className="font-semibold">
                {fm(imp.confirmNew, { count: counts.new, account: account?.display_name ?? "" })}
              </li>
              <li>{fm(imp.confirmDuplicates, { count: counts.duplicate })}</li>
              <li>{fm(imp.confirmErrors, { count: skipErrors ? counts.error : 0 })}</li>
              {blocked ? <li className="text-fg-danger">{fm(imp.confirmBlocked)}</li> : null}
            </ul>
          )}
          <div className="flex gap-3">
            {finished ? (
              <Link
                href={`/o/${org}/banking/${accountId}`}
                className="rounded-md bg-surface-accent px-4 py-2 text-sm font-semibold text-fg"
              >
                {fm(imp.viewAccount)}
              </Link>
            ) : (
              <>
                <Button variant="ghost" onClick={() => setStep(3)}>
                  {fm(imp.previous)}
                </Button>
                <Button variant="primary" disabled={busy || blocked} onClick={() => void commit()}>
                  {busy ? fm(imp.importing) : fm(imp.importButton, { count: counts.new })}
                </Button>
              </>
            )}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function detectionText(upload: Upload, fm: ReturnType<typeof useFormatMessage>): string {
  const lines = upload.lines;
  if (!upload.tabular) return fm(imp.detectedOfx, { format: upload.format.toUpperCase(), lines });
  if (upload.format === "xlsx") return fm(imp.detectedXlsx, { lines });
  const delimiter =
    upload.delimiter === ";"
      ? fm(imp.delimiterSemicolon)
      : upload.delimiter === "\t"
        ? fm(imp.delimiterTab)
        : upload.delimiter === "|"
          ? fm(imp.delimiterPipe)
          : fm(imp.delimiterComma);
  return fm(imp.detectedTable, {
    format: upload.format.toUpperCase(),
    encoding: ENCODINGS[upload.encoding] ?? upload.encoding,
    delimiter,
    lines,
  });
}

function LinesTable({
  lines,
  total,
  money,
  day,
}: {
  lines: PreviewLine[];
  total: number;
  money: (value: string | null) => string;
  day: (value: string | null) => string;
}) {
  const fm = useFormatMessage();
  if (total === 0) return <p className="p-4 text-sm text-fg-muted">{fm(imp.noLines)}</p>;
  return (
    <div className="flex flex-col gap-2">
      {lines.length < total ? (
        <p className="text-xs text-fg-muted">{fm(imp.moreLines, { shown: lines.length, total })}</p>
      ) : null}
      <table className="min-w-full text-sm" data-preview-lines="">
        <thead>
          <tr className="text-start text-xs text-fg-muted">
            <th scope="col" className="p-2 text-start">
              {fm(imp.colRow)}
            </th>
            <th scope="col" className="p-2 text-start">
              {fm(imp.colDate)}
            </th>
            <th scope="col" className="p-2 text-start">
              {fm(imp.colDescription)}
            </th>
            <th scope="col" className="p-2 text-end">
              {fm(imp.colAmount)}
            </th>
            <th scope="col" className="p-2 text-start">
              {fm(imp.colReason)}
            </th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => (
            <tr key={line.row} className="border-t border-border" data-line-status={line.status}>
              <td className="p-2 tabular-nums">{line.row}</td>
              <td className="p-2">{day(line.date)}</td>
              <td className="p-2">{line.description}</td>
              <td className="p-2 text-end tabular-nums">{money(line.amount)}</td>
              <td className="p-2 text-fg-muted">
                {line.reasons.map((reason) => reason.message).join(" ")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Control({ id, label, children }: { id: string; label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs font-medium text-fg-muted">
        {label}
      </label>
      {children}
    </div>
  );
}
