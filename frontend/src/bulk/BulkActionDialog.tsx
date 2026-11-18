"use client";

/**
 * A bulk action, step by step (V-03-T09): the action's parameters, then the **preview** — the
 * server's counts (will change / no change / skipped) and the diff table, field by field
 * current → new, for the first 50 organisations with the total — then *Apply*, which confirms
 * the job and hands it to the progress drawer (V-03-T10). Nothing changes before *Apply*.
 */
import { Button, Dialog } from "@numo9/ui";
import { useEffect, useId, useState, type ReactNode } from "react";

import { groupsApi, type Group, type Tag } from "@/groups/api";
import { useFormatMessage, type MessageDescriptor } from "@/i18n";

import { bulkApi, diffText, type ApiRefusal, type BulkJob, type BulkPreview } from "./api";
import { m } from "./messages";
import type { BulkActionKey } from "./SelectionBar";
import { selectionBody, selectionSize, type BulkSelection } from "./selection";
import { staffApi, type StaffMember } from "./staff";

export interface BulkActionDialogProps {
  practice: string;
  action: BulkActionKey;
  selection: BulkSelection;
  onClose: () => void;
  /** The confirmed job (the progress drawer takes over). */
  onStarted: (job: BulkJob) => void;
}

const TERMS: [string, MessageDescriptor][] = [
  ["days_after_document", m.daysAfterDocument],
  ["days_after_month_end", m.daysAfterMonthEnd],
  ["day_of_following_month", m.dayOfFollowingMonth],
  ["day_of_current_month", m.dayOfCurrentMonth],
];

type Params = Record<string, unknown>;

export function BulkActionDialog({
  practice,
  action,
  selection,
  onClose,
  onStarted,
}: BulkActionDialogProps) {
  const fm = useFormatMessage();
  const [params, setParams] = useState<Params>(() => initialParams(action));
  const [step, setStep] = useState<"form" | "preview">("form");
  const [result, setResult] = useState<{ job: BulkJob; preview: BulkPreview } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const errorId = useId();

  const previewIt = async () => {
    setBusy(true);
    const response = await bulkApi.create({
      practice,
      action,
      params,
      selection: selectionBody(selection),
    });
    setBusy(false);
    if (response.status === 201) {
      setResult(response.body as { job: BulkJob; preview: BulkPreview });
      setError(null);
      setStep("preview");
    } else setError((response.body as ApiRefusal | undefined)?.detail ?? fm(m.failed));
  };

  const apply = async () => {
    if (!result) return;
    setBusy(true);
    const response = await bulkApi.confirm(result.job.id);
    setBusy(false);
    if (response.status === 202) onStarted(response.body as BulkJob);
    else setError((response.body as ApiRefusal | undefined)?.detail ?? fm(m.failed));
  };

  const title = fm(m.dialogTitle, { action: fm(m[action]), count: selectionSize(selection) });
  const footer =
    step === "form" ? (
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={onClose}>
          {fm(m.cancel)}
        </Button>
        <Button variant="primary" loading={busy} onClick={() => void previewIt()}>
          {fm(m.previewButton)}
        </Button>
      </div>
    ) : (
      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={() => setStep("form")}>
          {fm(m.back)}
        </Button>
        <Button
          variant="primary"
          loading={busy}
          disabled={!result || result.preview.counts.change === 0}
          onClick={() => void apply()}
        >
          {fm(m.apply, { count: result?.preview.counts.change ?? 0 })}
        </Button>
      </div>
    );

  return (
    <Dialog
      open
      onOpenChange={(open) => (open ? undefined : onClose())}
      title={title}
      closeLabel={fm(m.close)}
      size="lg"
      footer={footer}
    >
      <div className="flex flex-col gap-4" data-bulk-dialog={step}>
        {step === "form" ? (
          <ActionForm practice={practice} action={action} params={params} onChange={setParams} />
        ) : result ? (
          <PreviewTable preview={result.preview} />
        ) : null}
        {error ? (
          <p id={errorId} role="alert" className="text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
      </div>
    </Dialog>
  );
}

function initialParams(action: BulkActionKey): Params {
  switch (action) {
    case "group":
      return { group: "", mode: "move" };
    case "tags":
      return { add: [], remove: [] };
    case "staff":
      return { member: "", mode: "assign" };
    case "settings":
      return { settings: { sales_terms: { type: "days_after_document", days: 30 } } };
    case "message":
      return { subject: "", body: "" };
    case "export":
      return { format: "csv" };
  }
}

// ---- the preview -------------------------------------------------------------------------------

function PreviewTable({ preview }: { preview: BulkPreview }) {
  const fm = useFormatMessage();
  const status = { change: m.statusChange, no_change: m.statusNoChange, skipped: m.statusSkipped };
  return (
    <div className="flex flex-col gap-3" data-bulk-preview="">
      <p className="text-sm text-fg-muted">{fm(m.nothingYet)}</p>
      <ul className="flex flex-wrap gap-2" aria-label={fm(m.colChange)}>
        <li className="rounded-full bg-surface-success-subtle px-3 py-1 text-sm font-semibold">
          {fm(m.willChange, { count: preview.counts.change })}
        </li>
        <li className="rounded-full bg-surface-muted px-3 py-1 text-sm font-semibold">
          {fm(m.noChange, { count: preview.counts.no_change })}
        </li>
        <li className="rounded-full bg-surface-danger-subtle px-3 py-1 text-sm font-semibold">
          {fm(m.skipped, { count: preview.counts.skipped })}
        </li>
      </ul>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-xs text-fg-muted">
            <th className="py-2 text-start">{fm(m.colOrganisation)}</th>
            <th className="py-2 text-start">{fm(m.colChange)}</th>
            <th className="py-2 text-start">{fm(m.colCurrent)}</th>
            <th className="py-2 text-start">{fm(m.colNew)}</th>
          </tr>
        </thead>
        <tbody>
          {preview.lines.map((line) => {
            const fields = diffText(line.before, line.after);
            return (
              <tr
                key={line.organisation.id}
                className="border-b border-border align-top"
                data-line={line.status}
              >
                <td className="py-2 font-semibold">{line.organisation.name}</td>
                <td className="py-2">
                  {fm(status[line.status])}
                  {line.message ? (
                    <span className="block text-xs text-fg-muted">{line.message}</span>
                  ) : null}
                </td>
                <td className="py-2">
                  {fields.map((field) => (
                    <span key={field.field} className="block">
                      {field.before}
                    </span>
                  ))}
                </td>
                <td className="py-2">
                  {fields.map((field) => (
                    <span key={field.field} className="block font-semibold">
                      {field.after}
                    </span>
                  ))}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-xs text-fg-muted">
        {fm(m.showing, { shown: preview.lines.length, total: preview.total })}
      </p>
    </div>
  );
}

// ---- the parameter forms -----------------------------------------------------------------------

interface FormProps {
  practice: string;
  action: BulkActionKey;
  params: Params;
  onChange: (params: Params) => void;
}

const control = "min-h-touch-target rounded-md border border-border-strong bg-surface px-2 text-sm";

function Labelled({ label, children }: { label: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className="grid gap-1">
      <label htmlFor={id} className="text-sm font-semibold">
        {label}
      </label>
      {children(id)}
    </div>
  );
}

function ActionForm({ practice, action, params, onChange }: FormProps) {
  const fm = useFormatMessage();
  const [groups, setGroups] = useState<Group[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [staff, setStaff] = useState<StaffMember[]>([]);
  useEffect(() => {
    if (action === "group")
      void groupsApi.list(practice).then((r) => r.status === 200 && setGroups(r.body.groups));
    if (action === "tags")
      void groupsApi.tags(practice).then((r) => r.status === 200 && setTags(r.body.tags));
    if (action === "staff")
      void staffApi.list(practice).then((r) => r.status === 200 && setStaff(r.body.staff));
  }, [action, practice]);
  const set = (key: string, value: unknown) => onChange({ ...params, [key]: value });

  if (action === "group") {
    return (
      <>
        <Labelled label={fm(m.groupField)}>
          {(id) => (
            <select
              id={id}
              className={control}
              value={String(params.group)}
              onChange={(e) => set("group", e.target.value)}
            >
              <option value="">{fm(m.choose)}</option>
              {groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {"— ".repeat(group.depth) + group.name}
                </option>
              ))}
            </select>
          )}
        </Labelled>
        <Labelled label={fm(m.mode)}>
          {(id) => (
            <select
              id={id}
              className={control}
              value={String(params.mode)}
              onChange={(e) => set("mode", e.target.value)}
            >
              <option value="move">{fm(m.modeMove)}</option>
              <option value="add">{fm(m.modeAdd)}</option>
              <option value="remove">{fm(m.modeRemove)}</option>
            </select>
          )}
        </Labelled>
      </>
    );
  }
  if (action === "tags") {
    const toggle = (which: "add" | "remove", id: string) => {
      const current = new Set(params[which] as string[]);
      const other = new Set(params[which === "add" ? "remove" : "add"] as string[]);
      if (current.has(id)) current.delete(id);
      else {
        current.add(id);
        other.delete(id);
      }
      onChange({
        ...params,
        [which]: [...current],
        [which === "add" ? "remove" : "add"]: [...other],
      });
    };
    if (!tags.length) return <p className="text-sm text-fg-muted">{fm(m.noTags)}</p>;
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        {(["add", "remove"] as const).map((which) => (
          <fieldset key={which} className="flex flex-col gap-1">
            <legend className="mb-1 text-sm font-semibold">
              {fm(which === "add" ? m.addTags : m.removeTags)}
            </legend>
            {tags.map((tag) => (
              <label key={tag.id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={(params[which] as string[]).includes(tag.id)}
                  onChange={() => toggle(which, tag.id)}
                />
                {tag.name}
              </label>
            ))}
          </fieldset>
        ))}
      </div>
    );
  }
  if (action === "staff") {
    return (
      <>
        <Labelled label={fm(m.member)}>
          {(id) => (
            <select
              id={id}
              className={control}
              value={String(params.member)}
              onChange={(e) => set("member", e.target.value)}
            >
              <option value="">{fm(m.choose)}</option>
              {staff.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name || person.email}
                </option>
              ))}
            </select>
          )}
        </Labelled>
        <Labelled label={fm(m.mode)}>
          {(id) => (
            <select
              id={id}
              className={control}
              value={String(params.mode)}
              onChange={(e) => set("mode", e.target.value)}
            >
              <option value="assign">{fm(m.assign)}</option>
              <option value="unassign">{fm(m.unassign)}</option>
            </select>
          )}
        </Labelled>
      </>
    );
  }
  if (action === "settings") return <SettingsForm params={params} onChange={onChange} />;
  if (action === "message") {
    return (
      <>
        <Labelled label={fm(m.subject)}>
          {(id) => (
            <input
              id={id}
              className={control}
              maxLength={150}
              value={String(params.subject)}
              onChange={(e) => set("subject", e.target.value)}
            />
          )}
        </Labelled>
        <Labelled label={fm(m.body)}>
          {(id) => (
            <textarea
              id={id}
              className={`${control} min-h-32 py-2`}
              maxLength={5000}
              value={String(params.body)}
              onChange={(e) => set("body", e.target.value)}
            />
          )}
        </Labelled>
        <p className="text-xs text-fg-muted">{fm(m.messageHint)}</p>
      </>
    );
  }
  return (
    <Labelled label={fm(m.format)}>
      {(id) => (
        <select
          id={id}
          className={control}
          value={String(params.format)}
          onChange={(e) => set("format", e.target.value)}
        >
          <option value="csv">{fm(m.csv)}</option>
          <option value="xlsx">{fm(m.xlsx)}</option>
        </select>
      )}
    </Labelled>
  );
}

type SettingKey = "sales_terms" | "purchase_terms" | "time_format" | "fiscal_year_end";

function SettingsForm({ params, onChange }: { params: Params; onChange: (p: Params) => void }) {
  const fm = useFormatMessage();
  const settings = params.settings as Record<SettingKey, Record<string, unknown>>;
  const key = Object.keys(settings)[0] as SettingKey;
  const value = settings[key] ?? {};
  const defaults: Record<SettingKey, Record<string, unknown>> = {
    sales_terms: { type: "days_after_document", days: 30 },
    purchase_terms: { type: "days_after_document", days: 30 },
    time_format: { value: "12h" },
    fiscal_year_end: { month: 12, day: 31 },
  };
  const put = (next: Record<string, unknown>) =>
    onChange({ settings: { [key]: { ...value, ...next } } });
  const names: Record<SettingKey, MessageDescriptor> = {
    sales_terms: m.salesTerms,
    purchase_terms: m.purchaseTerms,
    time_format: m.timeFormat,
    fiscal_year_end: m.fiscalYearEnd,
  };
  return (
    <>
      <Labelled label={fm(m.setting)}>
        {(id) => (
          <select
            id={id}
            className={control}
            value={key}
            onChange={(e) => {
              const next = e.target.value as SettingKey;
              onChange({ settings: { [next]: defaults[next] } });
            }}
          >
            {(Object.keys(names) as SettingKey[]).map((name) => (
              <option key={name} value={name}>
                {fm(names[name])}
              </option>
            ))}
          </select>
        )}
      </Labelled>
      {key === "sales_terms" || key === "purchase_terms" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <Labelled label={fm(m.days)}>
            {(id) => (
              <input
                id={id}
                inputMode="numeric"
                className={control}
                value={String(value.days ?? "")}
                onChange={(e) => put({ days: e.target.value })}
              />
            )}
          </Labelled>
          <Labelled label={fm(m.termsType)}>
            {(id) => (
              <select
                id={id}
                className={control}
                value={String(value.type)}
                onChange={(e) => put({ type: e.target.value })}
              >
                {TERMS.map(([type, label]) => (
                  <option key={type} value={type}>
                    {fm(label)}
                  </option>
                ))}
              </select>
            )}
          </Labelled>
        </div>
      ) : key === "time_format" ? (
        <Labelled label={fm(m.timeFormat)}>
          {(id) => (
            <select
              id={id}
              className={control}
              value={String(value.value)}
              onChange={(e) => put({ value: e.target.value })}
            >
              <option value="12h">{fm(m.h12)}</option>
              <option value="24h">{fm(m.h24)}</option>
            </select>
          )}
        </Labelled>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          <Labelled label={fm(m.month)}>
            {(id) => (
              <input
                id={id}
                inputMode="numeric"
                className={control}
                value={String(value.month ?? "")}
                onChange={(e) => put({ month: e.target.value })}
              />
            )}
          </Labelled>
          <Labelled label={fm(m.day)}>
            {(id) => (
              <input
                id={id}
                inputMode="numeric"
                className={control}
                value={String(value.day ?? "")}
                onChange={(e) => put({ day: e.target.value })}
              />
            )}
          </Labelled>
        </div>
      )}
    </>
  );
}
