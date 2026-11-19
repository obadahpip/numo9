"use client";

/**
 * Contacts import wizard (B-03-T12, wireframe "Contact import wizard"): 1 Upload (contacts or
 * people, template download and plain-language help, B-03-T13) → 2 Match columns (suggested
 * mapping with sample values, opt-in BN matching, save the mapping) → 3 Review (dry run totals,
 * rows filterable by action with their changes and reasons, errors as CSV) → 4 Import (background
 * job, status). Nothing is written before step 4.
 */
import { Button, Checkbox, Input, RadioGroup, Select } from "@numo9/ui";
import { useEffect, useId, useState, type FormEvent } from "react";

import { firstError } from "@/contacts/api";
import { useFormatMessage } from "@/i18n";

import {
  errorsCsvUrl,
  importsApi,
  templateUrl,
  type ImportEntity,
  type ImportRow,
  type ImportRun,
  type RowAction,
} from "./api";
import { m } from "./messages";

type Step = 1 | 2 | 3 | 4;
const ACTIONS: RowAction[] = ["create", "update", "unchanged", "error"];

export function ImportWizard({ org }: { org: string }) {
  const fm = useFormatMessage();
  const id = useId();
  const [step, setStep] = useState<Step>(1);
  const [entity, setEntity] = useState<ImportEntity>("contacts.contact");
  const [file, setFile] = useState<File | null>(null);
  const [run, setRun] = useState<ImportRun | null>(null);
  const [columns, setColumns] = useState<Record<string, string>>({});
  const [matchBn, setMatchBn] = useState(false);
  const [saveAs, setSaveAs] = useState("");
  const [rows, setRows] = useState<ImportRow[]>([]);
  const [filter, setFilter] = useState<RowAction | "all">("all");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  const names = [fm(m.stepUpload), fm(m.stepMap), fm(m.stepReview), fm(m.stepImport)];
  const actionLabel: Record<RowAction, string> = {
    create: fm(m.actionCreate),
    update: fm(m.actionUpdate),
    unchanged: fm(m.actionUnchanged),
    error: fm(m.actionError),
  };

  useEffect(() => {
    if (step !== 3 || !run) return;
    void importsApi.rows(org, run.id, filter === "all" ? undefined : filter).then((result) => {
      if (result.status === 200) setRows(result.body.results);
    });
  }, [org, run, step, filter]);

  useEffect(() => {
    if (step !== 4 || !run || run.status === "applied") return;
    const timer = setInterval(() => {
      void importsApi.get(org, run.id).then((result) => {
        if (result.status === 200 && result.body.status === "applied") {
          setRun(result.body);
          setStatus(fm(m.done));
        }
      });
    }, 2000);
    return () => clearInterval(timer);
  }, [org, run, step, fm]);

  const upload = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    setBusy(true);
    setError("");
    const result = await importsApi.upload(org, entity, file);
    setBusy(false);
    if (result.status === 201) {
      setRun(result.body);
      setColumns(result.body.columns);
      setStep(2);
    } else {
      setError(fm(m.uploadFailed, { reason: firstError(result.body) ?? "" }));
    }
  };

  const check = async () => {
    if (!run) return;
    setBusy(true);
    setError("");
    const result = await importsApi.dryRun(org, run.id, columns, matchBn, saveAs);
    setBusy(false);
    if (result.status === 200) {
      setRun({ ...run, ...result.body });
      setRows(result.body.results);
      setFilter("all");
      setStep(3);
    } else {
      setError(fm(m.failed, { reason: firstError(result.body) ?? "" }));
    }
  };

  const apply = async () => {
    if (!run) return;
    setBusy(true);
    const result = await importsApi.apply(org, run.id);
    setBusy(false);
    if (result.status === 202) {
      setRun({ ...run, ...result.body });
      setStatus(result.body.status === "applied" ? fm(m.done) : fm(m.importing));
      setStep(4);
    } else {
      setError(fm(m.failed, { reason: firstError(result.body) ?? "" }));
    }
  };

  const counts = run?.counts ?? {};
  const toImport = (counts.create ?? 0) + (counts.update ?? 0);
  const fieldOptions = [
    { value: "none", label: fm(m.notImported) },
    ...(run?.fields ?? []).map((f) => ({ value: f.key, label: f.label })),
  ];

  return (
    <div className="flex max-w-4xl flex-col gap-6" data-import-wizard="">
      <h1 className="text-2xl font-bold text-fg">{fm(m.title)}</h1>
      <ol aria-label={fm(m.steps)} className="flex flex-wrap gap-4 text-sm">
        {names.map((name, index) => (
          <li
            key={name}
            aria-current={step === index + 1 ? "step" : undefined}
            className={step === index + 1 ? "font-semibold text-fg" : "text-fg-muted"}
          >
            {fm(m.stepItem, { n: index + 1, name })}
          </li>
        ))}
      </ol>
      <h2 className="text-lg font-semibold">
        {fm(m.step, { n: step, name: names[step - 1] ?? "" })}
      </h2>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}

      {step === 1 ? (
        <form onSubmit={(event) => void upload(event)} className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 text-sm">
            <span id={`${id}-what`}>{fm(m.what)}</span>
            <RadioGroup
              aria-labelledby={`${id}-what`}
              value={entity}
              onValueChange={(value) => setEntity(value as ImportEntity)}
              options={[
                { value: "contacts.contact", label: fm(m.entityContacts) },
                { value: "contacts.person", label: fm(m.entityPeople) },
              ]}
            />
          </div>
          <label className="flex flex-col gap-1 text-sm">
            {fm(m.file)}
            <input
              type="file"
              accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <a href={templateUrl(org, entity)} className="text-sm font-semibold underline" download>
            {fm(m.template)}
          </a>
          <ul className="list-disc ps-5 text-sm text-fg-muted" data-import-help="">
            <li>{fm(m.help1)}</li>
            <li>{fm(m.help2)}</li>
            <li>{fm(m.help3)}</li>
          </ul>
          <div>
            <Button type="submit" variant="primary" disabled={!file || busy}>
              {fm(m.upload)}
            </Button>
          </div>
        </form>
      ) : null}

      {step === 2 && run ? (
        <div className="flex flex-col gap-4">
          <ul className="flex flex-col gap-3">
            {run.headers.map((header) => (
              <li key={header} className="grid gap-2 md:grid-cols-2 md:items-center">
                <div className="text-sm">
                  <span className="font-semibold">{header}</span>
                  <span className="block text-xs text-fg-muted">
                    {fm(m.sampleValues, {
                      values: (run.samples?.[header] ?? []).filter(Boolean).join(", ") || "—",
                    })}
                  </span>
                </div>
                <Select
                  aria-label={fm(m.columnFor, { header })}
                  value={columns[header] || "none"}
                  onValueChange={(value) =>
                    setColumns((current) => ({
                      ...current,
                      [header]: value === "none" ? "" : value,
                    }))
                  }
                  options={fieldOptions}
                />
              </li>
            ))}
          </ul>
          {run.entity === "contacts.contact" ? (
            <Checkbox
              label={fm(m.matchBn)}
              checked={matchBn}
              onCheckedChange={(checked) => setMatchBn(checked === true)}
            />
          ) : null}
          <label className="flex max-w-sm flex-col gap-1 text-sm">
            {fm(m.saveAs)}
            <Input value={saveAs} onChange={(event) => setSaveAs(event.target.value)} />
          </label>
          <div className="flex gap-2">
            <Button onClick={() => setStep(1)}>{fm(m.back)}</Button>
            <Button variant="primary" disabled={busy} onClick={() => void check()}>
              {fm(m.check)}
            </Button>
          </div>
        </div>
      ) : null}

      {step === 3 && run ? (
        <div className="flex flex-col gap-4">
          <p role="status" className="text-sm" data-import-totals="">
            {fm(m.totals, {
              create: counts.create ?? 0,
              update: counts.update ?? 0,
              unchanged: counts.unchanged ?? 0,
              error: counts.error ?? 0,
            })}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Select
              aria-label={fm(m.filter)}
              value={filter}
              onValueChange={(value) => setFilter(value as RowAction | "all")}
              options={[
                { value: "all", label: fm(m.filterAll) },
                ...ACTIONS.map((action) => ({ value: action, label: actionLabel[action] })),
              ]}
            />
            {(counts.error ?? 0) > 0 ? (
              <a
                href={errorsCsvUrl(org, run.id)}
                className="text-sm font-semibold underline"
                download
              >
                {fm(m.errorsCsv)}
              </a>
            ) : null}
          </div>
          <ul className="flex flex-col divide-y divide-border rounded-md border border-border">
            {rows.map((row) => (
              <li
                key={row.row}
                className="flex flex-col gap-1 p-3 text-sm"
                data-action={row.action}
              >
                <span className="font-semibold">
                  {fm(m.rowLine, {
                    action: actionLabel[row.action],
                    row: row.row,
                    label: row.label || row.key,
                  })}
                </span>
                {Object.entries(row.changes).map(([field, [before, after]]) => (
                  <span key={field} className="text-fg-muted">
                    {fm(m.change, {
                      field,
                      before: String(before ?? "") || "—",
                      after: String(after ?? "") || "—",
                    })}
                  </span>
                ))}
                {row.errors.map((problem) => (
                  <span key={`${problem.field}-${problem.code}`} className="text-fg-danger">
                    {problem.message}
                  </span>
                ))}
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <Button onClick={() => setStep(2)}>{fm(m.back)}</Button>
            <Button
              variant="primary"
              disabled={busy || toImport === 0}
              onClick={() => void apply()}
            >
              {fm(m.importNow, { count: toImport })}
            </Button>
          </div>
        </div>
      ) : null}

      {step === 4 ? (
        <p role="status" className="text-sm" data-import-status="">
          {status}
        </p>
      ) : null}
    </div>
  );
}
