"use client";

import { Button, ErrorState, Input, LoadingRegion, Select, SkeletonTable } from "@numo9/ui";
import Link from "next/link";
import { useCallback, useEffect, useId, useState } from "react";

import { RecordHistory } from "@/audit/RecordHistory";
import { defineMessages, useFormatMessage } from "@/i18n";

import type { FieldErrors } from "./api";
import {
  addRegistration,
  listRegistrations,
  removeRegistration,
  updateRegistration,
  type Registration,
  type RegistrationInput,
  type RegistrationRefusal,
} from "./registrations";

const m = defineMessages({
  title: {
    id: "settings.registrations.title",
    defaultMessage: "Tax registrations",
    description: "Page heading",
  },
  intro: {
    id: "settings.registrations.intro",
    defaultMessage:
      "Every statutory number in one place: your Business Number (BN) and its program accounts (RT for GST/HST, RP for payroll, RC for corporate income tax), and provincial numbers (QST, PST, RST).",
    description: "Text under the heading",
  },
  type: {
    id: "settings.registrations.type",
    defaultMessage: "Registration",
    description: "Column / field",
  },
  number: {
    id: "settings.registrations.number",
    defaultMessage: "Number",
    description: "Column / field",
  },
  numberHint: {
    id: "settings.registrations.numberHint",
    defaultMessage: "BN: 9 digits. Program accounts: 123456789 RT 0001.",
    description: "Hint",
  },
  from: {
    id: "settings.registrations.from",
    defaultMessage: "Effective from",
    description: "Column / field",
  },
  to: {
    id: "settings.registrations.to",
    defaultMessage: "Effective to",
    description: "Column / field",
  },
  status: {
    id: "settings.registrations.status",
    defaultMessage: "Status",
    description: "Column / field",
  },
  actions: {
    id: "settings.registrations.actions",
    defaultMessage: "Actions",
    description: "Column",
  },
  save: { id: "settings.registrations.save", defaultMessage: "Save", description: "Button" },
  saveRow: {
    id: "settings.registrations.saveRow",
    defaultMessage: "Save {registration}",
    description: "Accessible name of a row's save button",
  },
  remove: { id: "settings.registrations.remove", defaultMessage: "Remove", description: "Button" },
  removeRow: {
    id: "settings.registrations.removeRow",
    defaultMessage: "Remove {registration}",
    description: "Accessible name of a row's remove button",
  },
  add: {
    id: "settings.registrations.add",
    defaultMessage: "Add registration",
    description: "Button",
  },
  rowName: {
    id: "settings.registrations.rowName",
    defaultMessage: "{type} {number}",
    description: "A registration's name in its history drawer",
  },
  newRow: {
    id: "settings.registrations.newRow",
    defaultMessage: "New registration",
    description: "Row label",
  },
  empty: {
    id: "settings.registrations.empty",
    defaultMessage: "No tax registrations yet. Add your Business Number first.",
    description: "Empty state",
  },
  saved: {
    id: "settings.registrations.saved",
    defaultMessage: "{registration} saved.",
    description: "Status",
  },
  removed: {
    id: "settings.registrations.removed",
    defaultMessage: "{registration} removed.",
    description: "Status",
  },
  failed: {
    id: "settings.registrations.failed",
    defaultMessage: "That didn't work. Try again in a moment.",
    description: "Status",
  },
  loading: {
    id: "settings.registrations.loading",
    defaultMessage: "Loading tax registrations…",
    description: "Loading",
  },
  loadFailed: {
    id: "settings.registrations.loadFailed",
    defaultMessage: "Tax registrations couldn't be loaded",
    description: "Error",
  },
  loadFailedBody: {
    id: "settings.registrations.loadFailedBody",
    defaultMessage: "Verify your connection, then try again.",
    description: "Error body",
  },
  retry: { id: "settings.registrations.retry", defaultMessage: "Try again", description: "Retry" },
  typeOption: {
    id: "settings.registrations.typeOption",
    defaultMessage:
      "{value, select, bn {Business Number (BN)} rt {GST/HST program account (RT)} rp {Payroll program account (RP)} rc {Corporate income tax program account (RC)} qst {Quebec QST number} pst_bc {British Columbia PST number} pst_sk {Saskatchewan PST number} rst_mb {Manitoba RST number} other {{value}}}",
    description: "Registration type",
  },
  statusOption: {
    id: "settings.registrations.statusOption",
    defaultMessage:
      "{value, select, pending {Applied for} active {Registered} closed {Closed} other {{value}}}",
    description: "Registration status",
  },
});

const fm2 = defineMessages({
  frequency: {
    id: "settings.registrations.frequency",
    defaultMessage: "Filing frequency",
    description: "Field on a new GST/HST or QST registration",
  },
  frequencyOption: {
    id: "settings.registrations.frequencyOption",
    defaultMessage: "{value, select, monthly {Monthly} quarterly {Quarterly} other {Annual}}",
    description: "Filing frequency option",
  },
  filing: {
    id: "settings.registrations.filing",
    defaultMessage:
      "{frequency, select, monthly {Files monthly} quarterly {Files quarterly} annual {Files annually} other {No filing frequency yet}}",
    description: "Filing summary on a registration",
  },
  nextDue: {
    id: "settings.registrations.nextDue",
    defaultMessage: "Next return due {date}",
    description: "Filing summary: next return due date",
  },
  overdue: {
    id: "settings.registrations.overdue",
    defaultMessage: "{count, plural, one {# return overdue} other {# returns overdue}}",
    description: "Filing summary: overdue returns",
  },
  filingLink: {
    id: "settings.registrations.filingLink",
    defaultMessage: "Filing periods",
    description: "Link to the registration's filing timeline (G-03a)",
  },
  filingLinkName: {
    id: "settings.registrations.filingLinkName",
    defaultMessage: "Filing periods of {registration}",
    description: "Accessible name of the filing periods link",
  },
  sectionTitle: {
    id: "settings.registrations.sectionTitle",
    defaultMessage: "Business number and registrations",
    description: "Card heading on the tax settings page",
  },
});

const FILING = ["rt", "qst"];
const FREQUENCIES = ["monthly", "quarterly", "annual"];
const TYPES = ["bn", "rt", "rp", "rc", "qst", "pst_bc", "pst_sk", "rst_mb"];
const STATUSES = ["pending", "active", "closed"];
const EMPTY: RegistrationInput = {
  type: "bn",
  number: "",
  effective_from: null,
  effective_to: null,
  status: "active",
  cra_approval_ref: "",
};

/**
 * Settings → Tax registrations (A-05-T12, gap-39): the one page for every statutory number — a
 * repeater with one editable row per registration (type, number, dates, status), each saved on
 * its own with the server's rules shown on the row, removed, and with its history drawer
 * (A-04-T10). No tax registration is edited anywhere else.
 */
export function RegistrationsScreen({
  org,
  embedded = false,
  onChanged,
}: Readonly<{
  org: string;
  /** Inside the tax settings page (G-06-T08): a card with an h2, not a page with an h1. */
  embedded?: boolean;
  /** Called after a registration is added, saved or removed. */
  onChanged?: () => void;
}>) {
  const fm = useFormatMessage();
  const [rows, setRows] = useState<Registration[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [status, setStatus] = useState("");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    setFailed(false);
    const answer = await listRegistrations(org);
    if (answer.status === 200 && Array.isArray(answer.body)) setRows(answer.body);
    else setFailed(true);
  }, [org]);
  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex max-w-3xl flex-col gap-2">
        {embedded ? (
          <h2 className="text-lg font-semibold">{fm(fm2.sectionTitle)}</h2>
        ) : (
          <h1 className="text-2xl font-semibold">{fm(m.title)}</h1>
        )}
        <p className="text-fg-muted">{fm(m.intro)}</p>
      </header>
      <p role="status" aria-live="polite" className="text-fg-muted" data-registrations-status>
        {status}
      </p>
      {failed ? (
        <ErrorState
          title={fm(m.loadFailed)}
          body={fm(m.loadFailedBody)}
          retryLabel={fm(m.retry)}
          onRetry={() => void load()}
        />
      ) : rows === null ? (
        <LoadingRegion label={fm(m.loading)}>
          <SkeletonTable rows={3} columns={6} />
        </LoadingRegion>
      ) : (
        <>
          {rows.length === 0 && !adding ? <p className="text-fg-muted">{fm(m.empty)}</p> : null}
          <ul className="flex flex-col gap-4" aria-label={fm(m.title)}>
            {rows.map((row) => (
              <RegistrationRow
                key={row.id}
                org={org}
                row={row}
                onSaved={(saved) => {
                  setRows(
                    (current) => current?.map((r) => (r.id === saved.id ? saved : r)) ?? null,
                  );
                  setStatus(fm(m.saved, { registration: saved.type_label }));
                  onChanged?.();
                }}
                onRemoved={() => {
                  setRows((current) => current?.filter((r) => r.id !== row.id) ?? null);
                  setStatus(fm(m.removed, { registration: row.type_label }));
                  onChanged?.();
                }}
              />
            ))}
            {adding ? (
              <RegistrationRow
                org={org}
                row={null}
                onSaved={(saved) => {
                  setRows((current) => [...(current ?? []), saved]);
                  setAdding(false);
                  setStatus(fm(m.saved, { registration: saved.type_label }));
                  onChanged?.();
                }}
                onRemoved={() => setAdding(false)}
              />
            ) : null}
          </ul>
          {adding ? null : (
            <Button className="self-start" onClick={() => setAdding(true)}>
              {fm(m.add)}
            </Button>
          )}
        </>
      )}
    </div>
  );
}

function RegistrationRow({
  org,
  row,
  onSaved,
  onRemoved,
}: Readonly<{
  org: string;
  row: Registration | null;
  onSaved: (row: Registration) => void;
  onRemoved: () => void;
}>) {
  const fm = useFormatMessage();
  const id = useId();
  const [value, setValue] = useState<RegistrationInput>(
    row
      ? {
          type: row.type,
          number: row.number,
          effective_from: row.effective_from,
          effective_to: row.effective_to,
          status: row.status,
          cra_approval_ref: row.cra_approval_ref,
        }
      : EMPTY,
  );
  const [errors, setErrors] = useState<FieldErrors>({});
  const [busy, setBusy] = useState(false);
  const name = row ? row.type_label : fm(m.newRow);

  const save = async () => {
    setBusy(true);
    setErrors({});
    const answer = row
      ? await updateRegistration(org, row.id, value)
      : await addRegistration(org, value);
    setBusy(false);
    if ((answer.status === 200 || answer.status === 201) && "id" in answer.body)
      onSaved(answer.body as Registration);
    else if (answer.status === 400) setErrors(answer.body as FieldErrors);
    else setErrors({ non_field_errors: [refusal(answer.body) ?? fm(m.failed)] });
  };
  const remove = async () => {
    if (!row) return onRemoved();
    const answer = await removeRegistration(org, row.id);
    if (answer.status === 204) onRemoved();
    else setErrors({ non_field_errors: [refusal(answer.body) ?? fm(m.failed)] });
  };
  const refusal = (body: unknown) => (body as RegistrationRefusal | null)?.detail || undefined;
  const files = FILING.includes(value.type);
  const error = (field: string) =>
    errors[field]?.[0] ? (
      <span id={`${id}-${field}-error`} className="text-sm text-fg-danger">
        {errors[field]![0]}
      </span>
    ) : null;
  const described = (field: string) => (errors[field]?.[0] ? `${id}-${field}-error` : undefined);
  const set = (field: keyof RegistrationInput, v: string | null) =>
    setValue((current) => ({ ...current, [field]: v }));

  return (
    <li
      className="grid gap-3 rounded-lg border border-border p-4 md:grid-cols-[14rem_1fr_9rem_9rem_9rem]"
      data-registration={row?.id ?? "new"}
      aria-label={name}
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-type`} className="text-sm font-medium">
          {fm(m.type)}
        </label>
        <Select
          id={`${id}-type`}
          value={value.type}
          onValueChange={(v) => set("type", v)}
          options={TYPES.map((t) => ({ value: t, label: fm(m.typeOption, { value: t }) }))}
          disabled={Boolean(row)}
        />
        {error("type")}
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-number`} className="text-sm font-medium">
          {fm(m.number)}
        </label>
        <Input
          id={`${id}-number`}
          value={value.number}
          onChange={(e) => set("number", e.target.value)}
          invalid={Boolean(errors.number)}
          aria-describedby={described("number") ?? `${id}-number-hint`}
        />
        <span id={`${id}-number-hint`} className="text-xs text-fg-muted">
          {fm(m.numberHint)}
        </span>
        {error("number")}
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-from`} className="text-sm font-medium">
          {fm(m.from)}
        </label>
        <Input
          id={`${id}-from`}
          type="date"
          value={value.effective_from ?? ""}
          onChange={(e) => set("effective_from", e.target.value || null)}
          aria-describedby={described("effective_from")}
        />
        {error("effective_from")}
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-to`} className="text-sm font-medium">
          {fm(m.to)}
        </label>
        <Input
          id={`${id}-to`}
          type="date"
          value={value.effective_to ?? ""}
          onChange={(e) => set("effective_to", e.target.value || null)}
          aria-describedby={described("effective_to")}
        />
        {error("effective_to")}
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-status`} className="text-sm font-medium">
          {fm(m.status)}
        </label>
        <Select
          id={`${id}-status`}
          value={value.status}
          onValueChange={(v) => set("status", v)}
          options={STATUSES.map((s) => ({ value: s, label: fm(m.statusOption, { value: s }) }))}
        />
      </div>
      {!row && files ? (
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-frequency`} className="text-sm font-medium">
            {fm(fm2.frequency)}
          </label>
          <Select
            id={`${id}-frequency`}
            value={value.frequency ?? "annual"}
            onValueChange={(v) => set("frequency", v)}
            options={FREQUENCIES.map((f) => ({
              value: f,
              label: fm(fm2.frequencyOption, { value: f }),
            }))}
          />
        </div>
      ) : null}
      {row?.files_returns ? (
        <p
          className="flex flex-wrap items-center gap-x-3 text-sm text-fg-muted md:col-span-5"
          data-filing
        >
          <span>{fm(fm2.filing, { frequency: row.filing?.frequency || "none" })}</span>
          {row.filing?.next_due ? (
            <span>{fm(fm2.nextDue, { date: row.filing.next_due.due_date })}</span>
          ) : null}
          {row.filing?.overdue ? (
            <span className="text-fg-danger">{fm(fm2.overdue, { count: row.filing.overdue })}</span>
          ) : null}
          <Link
            href={`/o/${org}/settings/tax/registrations/${row.id}/filing`}
            className="text-fg underline"
            aria-label={fm(fm2.filingLinkName, { registration: name })}
          >
            {fm(fm2.filingLink)}
          </Link>
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2 md:col-span-5">
        <Button
          size="sm"
          variant="primary"
          loading={busy}
          onClick={() => void save()}
          aria-label={fm(m.saveRow, { registration: name })}
        >
          {fm(m.save)}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => void remove()}
          aria-label={fm(m.removeRow, { registration: name })}
        >
          {fm(m.remove)}
        </Button>
        {row ? (
          <RecordHistory
            org={org}
            type="orgsettings.TaxRegistration"
            id={row.id}
            label={fm(m.rowName, { type: row.type_label, number: row.display_number })}
          />
        ) : null}
        {errors.non_field_errors?.[0] ? (
          <span role="alert" className="text-sm text-fg-danger">
            {errors.non_field_errors[0]}
          </span>
        ) : null}
      </div>
    </li>
  );
}
