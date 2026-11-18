"use client";

/**
 * Contact form (B-01-T15, wireframe 13): one page with section anchors (Details, People, Addresses,
 * Financial, Sales and purchase defaults), role chips, unlimited people with one primary, billing
 * and shipping addresses with the province picker and postal-code entry, credit limit with
 * warn/block, default accounts filtered by side (sales: revenue…; purchase: expenses and assets).
 * While the name, email or BN is typed, possible duplicates show with Open · Merge… · Ignore
 * (B-01-T16, T17). Server refusals land on their fields.
 */
import {
  AccountPicker,
  Button,
  Checkbox,
  ErrorState,
  Input,
  PostalCodeInput,
  ProvincePicker,
  RadioGroup,
  type AppLocale,
  type PickerAccount,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useId, useState, type FormEvent, type ReactNode } from "react";

import { accountsApi } from "@/accounts/api";
import { useFormatMessage } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

import {
  contactsApi,
  fieldErrors,
  type AddressRow,
  type ContactDetail,
  type ContactPersonRow,
  type ContactRoleKey,
  type ContactWrite,
} from "./api";
import { contactUrl } from "./ContactsScreen";
import { DuplicatePanel } from "./DuplicatePanel";
import { fmsg } from "./formMessages";
import { MergeDialog } from "./MergeDialog";
import { ROLE_LABEL, ROLES } from "./roles";
import { useDuplicateCheck } from "./useDuplicateCheck";

const emptyPerson = (primary: boolean): ContactPersonRow => ({
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  job_title: "",
  is_primary: primary,
  include_in_emails: true,
});
const emptyAddress = (kind: "billing" | "shipping"): AddressRow => ({
  kind,
  attention: "",
  line1: "",
  line2: "",
  city: "",
  province: "",
  region: "",
  postal_code: "",
  country: "CA",
});

interface FormState {
  display_name: string;
  legal_name: string;
  roles: ContactRoleKey[];
  bn: string;
  tax_id: string;
  currency: string;
  credit_limit: string;
  credit_mode: "warn" | "block";
  sales_account: string | null;
  purchase_account: string | null;
  people: ContactPersonRow[];
  addresses: AddressRow[];
}

function fromDetail(contact: ContactDetail | null): FormState {
  const addresses = contact?.addresses ?? [];
  return {
    display_name: contact?.display_name ?? "",
    legal_name: contact?.legal_name ?? "",
    roles: contact?.roles ?? ["customer"],
    bn: contact?.bn ?? "",
    tax_id: contact?.tax_id ?? "",
    currency: contact?.currency ?? "CAD",
    credit_limit: contact?.credit_limit ?? "",
    credit_mode: contact?.credit_mode ?? "warn",
    sales_account: contact?.sales_account?.id ?? null,
    purchase_account: contact?.purchase_account?.id ?? null,
    people: contact?.people.length ? contact.people : [emptyPerson(true)],
    addresses: (["billing", "shipping"] as const).map(
      (kind) => addresses.find((a) => a.kind === kind) ?? emptyAddress(kind),
    ),
  };
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="flex scroll-mt-24 flex-col gap-3">
      <h2 id={`${id}-heading`} className="text-lg font-semibold text-fg">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Text({
  label,
  value,
  onChange,
  error,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  type?: string;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1 text-sm">
      <label htmlFor={id}>{label}</label>
      <Input
        id={id}
        type={type}
        value={value}
        invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {error ? (
        <span id={`${id}-error`} className="text-xs text-fg-danger">
          {error}
        </span>
      ) : null}
    </div>
  );
}

export function ContactForm({ org, id }: { org: string; id?: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [contact, setContact] = useState<ContactDetail | null>(null);
  const [form, setForm] = useState<FormState>(fromDetail(null));
  const [loaded, setLoaded] = useState(!id);
  const [loadFailed, setLoadFailed] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [accounts, setAccounts] = useState<PickerAccount[]>([]);
  const [merging, setMerging] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    void contactsApi.get(org, id).then((result) => {
      if (result.status === 200) {
        setContact(result.body);
        setForm(fromDetail(result.body));
        setLoaded(true);
      } else {
        setLoadFailed(true);
      }
    });
  }, [org, id]);

  useEffect(() => {
    void accountsApi.list(org, "active").then((result) => {
      if (result.status !== 200 || !Array.isArray(result.body?.results)) return;
      setAccounts(
        result.body.results.map((a) => ({
          id: a.id,
          code: a.code,
          name: a.name,
          type: a.type,
          subtype: a.subtype as PickerAccount["subtype"],
          detail: a.subtype_label,
          systemRole: a.system_role || undefined,
          isBank: a.is_bank,
          depth: a.depth,
          postable: !a.has_children,
        })),
      );
    });
  }, [org]);

  const duplicates = useDuplicateCheck(org, {
    name: form.display_name,
    email: form.people[0]?.email,
    bn: form.bn,
    exclude: id,
  });

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((current) => ({ ...current, [key]: value }));
  const setPerson = (index: number, change: Partial<ContactPersonRow>) =>
    setForm((current) => ({
      ...current,
      people: current.people.map((p, i) =>
        i === index ? { ...p, ...change } : change.is_primary ? { ...p, is_primary: false } : p,
      ),
    }));
  const setAddress = (index: number, change: Partial<AddressRow>) =>
    setForm((current) => ({
      ...current,
      addresses: current.addresses.map((a, i) => (i === index ? { ...a, ...change } : a)),
    }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const body: ContactWrite = {
      display_name: form.display_name,
      legal_name: form.legal_name,
      roles: form.roles,
      bn: form.bn,
      tax_id: form.tax_id,
      currency: form.currency,
      credit_limit: form.credit_limit.trim() || null,
      credit_mode: form.credit_mode,
      sales_account: form.sales_account,
      purchase_account: form.purchase_account,
      people: form.people.filter((p) => p.first_name || p.last_name || p.email),
      addresses: form.addresses.filter((a) => a.line1 || a.city || a.province || a.postal_code),
    };
    setBusy(true);
    const result = id
      ? await contactsApi.update(org, id, body)
      : await contactsApi.create(org, body);
    setBusy(false);
    if (result.status === 200 || result.status === 201) {
      setErrors({});
      setStatus(fm(fmsg.saved));
      if (!id) window.location.assign(contactUrl(org, result.body.id));
      else {
        setContact(result.body);
        setForm(fromDetail(result.body));
      }
    } else {
      const found = fieldErrors(result.body);
      setErrors(found);
      setStatus("");
      const first = Object.keys(found)[0];
      if (first) {
        document
          .querySelector<HTMLElement>(
            `[data-field="${first}"] input, [data-field="${first}"] button`,
          )
          ?.focus();
      }
    }
  };

  if (loadFailed) {
    return (
      <ErrorState
        title={fm(fmsg.loadFailed)}
        retryLabel={fm(fmsg.retry)}
        onRetry={() => window.location.reload()}
        headingLevel={2}
      />
    );
  }
  if (!loaded) return null;

  const typeLabels = {
    asset: fm(fmsg.typeAsset),
    liability: fm(fmsg.typeLiability),
    equity: fm(fmsg.typeEquity),
    revenue: fm(fmsg.typeRevenue),
    expense: fm(fmsg.typeExpense),
  };
  const anchors = [
    ["details", fmsg.details],
    ["people", fmsg.people],
    ["addresses", fmsg.addresses],
    ["financial", fmsg.financial],
    ["defaults", fmsg.defaults],
  ] as const;
  const summary = Object.values(errors)[0];

  return (
    <div className="flex flex-col gap-6" data-contact-form="">
      <a href={orgModuleUrl(org, "contacts")} className="text-sm font-semibold underline">
        {fm(fmsg.back)}
      </a>
      <h1 className="text-2xl font-bold text-fg">
        {contact ? contact.display_name : fm(fmsg.newTitle)}
      </h1>
      {contact?.merged_into ? (
        <p role="note" className="text-sm">
          <a href={contactUrl(org, contact.merged_into.id)} className="underline">
            {fm(fmsg.mergedInto, { name: contact.merged_into.name })}
          </a>
        </p>
      ) : null}
      <nav aria-label={fm(fmsg.sections)} className="flex flex-wrap gap-3 text-sm">
        {anchors.map(([anchor, label]) => (
          <a key={anchor} href={`#${anchor}`} className="underline">
            {fm(label)}
          </a>
        ))}
      </nav>
      {summary ? (
        <p role="alert" className="text-sm text-fg-danger">
          {fm(fmsg.fixErrors, { message: summary })}
        </p>
      ) : null}
      <form onSubmit={(event) => void submit(event)} className="flex max-w-3xl flex-col gap-8">
        <Section id="details" title={fm(fmsg.details)}>
          <div data-field="display_name">
            <Text
              label={fm(fmsg.displayName)}
              value={form.display_name}
              onChange={(value) => set("display_name", value)}
              error={errors.display_name}
            />
          </div>
          <DuplicatePanel
            org={org}
            matches={duplicates.matches}
            onMerge={id ? (match) => setMerging(match.contact.id) : undefined}
          />
          <Text
            label={fm(fmsg.legalName)}
            value={form.legal_name}
            onChange={(value) => set("legal_name", value)}
            error={errors.legal_name}
          />
          <fieldset className="flex flex-col gap-2" data-field="roles">
            <legend className="text-sm">{fm(fmsg.roles)}</legend>
            <div className="flex flex-wrap gap-4">
              {ROLES.map((role) => (
                <Checkbox
                  key={role}
                  label={fm(ROLE_LABEL[role])}
                  checked={form.roles.includes(role)}
                  onCheckedChange={(checked) =>
                    set(
                      "roles",
                      checked === true
                        ? [...form.roles, role]
                        : form.roles.filter((r) => r !== role),
                    )
                  }
                />
              ))}
            </div>
            {errors.roles ? <span className="text-xs text-fg-danger">{errors.roles}</span> : null}
          </fieldset>
          <div className="grid gap-3 md:grid-cols-3" data-field="bn">
            <Text
              label={fm(fmsg.bn)}
              value={form.bn}
              onChange={(v) => set("bn", v)}
              error={errors.bn}
            />
            <Text
              label={fm(fmsg.taxId)}
              value={form.tax_id}
              onChange={(v) => set("tax_id", v)}
              error={errors.tax_id}
            />
            <Text
              label={fm(fmsg.currency)}
              value={form.currency}
              onChange={(v) => set("currency", v.toUpperCase())}
              error={errors.currency}
            />
          </div>
        </Section>

        <Section id="people" title={fm(fmsg.people)}>
          {form.people.map((person, index) => (
            <fieldset
              key={person.id ?? `new-${index}`}
              className="flex flex-col gap-2 rounded-md border border-border p-3"
            >
              <legend className="px-1 text-sm font-semibold">
                {fm(fmsg.personLegend, { n: index + 1 })}
              </legend>
              <div className="grid gap-3 md:grid-cols-2">
                <Text
                  label={fm(fmsg.firstName)}
                  value={person.first_name}
                  onChange={(v) => setPerson(index, { first_name: v })}
                  error={errors[`people[${index}].first_name`]}
                />
                <Text
                  label={fm(fmsg.lastName)}
                  value={person.last_name}
                  onChange={(v) => setPerson(index, { last_name: v })}
                />
                <Text
                  label={fm(fmsg.email)}
                  type="email"
                  value={person.email}
                  onChange={(v) => setPerson(index, { email: v })}
                  error={errors[`people[${index}].email`]}
                />
                <Text
                  label={fm(fmsg.phone)}
                  value={person.phone}
                  onChange={(v) => setPerson(index, { phone: v })}
                  error={errors[`people[${index}].phone`]}
                />
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Checkbox
                  label={fm(fmsg.primary)}
                  checked={person.is_primary}
                  onCheckedChange={(checked) => setPerson(index, { is_primary: checked === true })}
                />
                {form.people.length > 1 ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() =>
                      set(
                        "people",
                        form.people.filter((_, i) => i !== index),
                      )
                    }
                  >
                    {fm(fmsg.removePerson, { n: index + 1 })}
                  </Button>
                ) : null}
              </div>
            </fieldset>
          ))}
          <div>
            <Button onClick={() => set("people", [...form.people, emptyPerson(false)])}>
              {fm(fmsg.addPerson)}
            </Button>
          </div>
        </Section>

        <Section id="addresses" title={fm(fmsg.addresses)}>
          {form.addresses.map((address, index) => {
            const key = (field: string) => errors[`addresses[${index}].${field}`];
            return (
              <fieldset
                key={address.kind}
                className="flex flex-col gap-2 rounded-md border border-border p-3"
              >
                <legend className="px-1 text-sm font-semibold">
                  {fm(address.kind === "billing" ? fmsg.billing : fmsg.shipping)}
                </legend>
                <Text
                  label={fm(fmsg.line1)}
                  value={address.line1}
                  onChange={(v) => setAddress(index, { line1: v })}
                  error={key("line1")}
                />
                <Text
                  label={fm(fmsg.line2)}
                  value={address.line2}
                  onChange={(v) => setAddress(index, { line2: v })}
                />
                <div className="grid gap-3 md:grid-cols-3">
                  <Text
                    label={fm(fmsg.city)}
                    value={address.city}
                    onChange={(v) => setAddress(index, { city: v })}
                    error={key("city")}
                  />
                  <div
                    className="flex flex-col gap-1 text-sm"
                    data-field={`addresses[${index}].province`}
                  >
                    <span id={`province-${address.kind}`}>{fm(fmsg.province)}</span>
                    <ProvincePicker
                      locale={locale}
                      groupLabels={{
                        provinces: fm(fmsg.provinces),
                        territories: fm(fmsg.territories),
                      }}
                      aria-labelledby={`province-${address.kind}`}
                      value={address.province || undefined}
                      onValueChange={(value) => setAddress(index, { province: value })}
                      invalid={Boolean(key("province"))}
                    />
                    {key("province") ? (
                      <span className="text-xs text-fg-danger">{key("province")}</span>
                    ) : null}
                  </div>
                  <div
                    className="flex flex-col gap-1 text-sm"
                    data-field={`addresses[${index}].postal_code`}
                  >
                    <label htmlFor={`postal-${address.kind}`}>{fm(fmsg.postalCode)}</label>
                    <PostalCodeInput
                      id={`postal-${address.kind}`}
                      value={address.postal_code}
                      onChange={(value) => setAddress(index, { postal_code: value })}
                      invalid={Boolean(key("postal_code"))}
                      aria-describedby={
                        key("postal_code") ? `postal-${address.kind}-error` : undefined
                      }
                    />
                    {key("postal_code") ? (
                      <span id={`postal-${address.kind}-error`} className="text-xs text-fg-danger">
                        {key("postal_code")}
                      </span>
                    ) : null}
                  </div>
                </div>
              </fieldset>
            );
          })}
        </Section>

        <Section id="financial" title={fm(fmsg.financial)}>
          <div className="grid gap-3 md:grid-cols-2">
            <Text
              label={fm(fmsg.creditLimit)}
              value={form.credit_limit}
              onChange={(v) => set("credit_limit", v)}
              error={errors.credit_limit}
            />
            <div className="flex flex-col gap-1 text-sm">
              <span id="credit-mode">{fm(fmsg.creditMode)}</span>
              <RadioGroup
                aria-labelledby="credit-mode"
                value={form.credit_mode}
                onValueChange={(value) => set("credit_mode", value as "warn" | "block")}
                options={[
                  { value: "warn", label: fm(fmsg.creditWarn) },
                  { value: "block", label: fm(fmsg.creditBlock) },
                ]}
                className="flex gap-4"
              />
            </div>
          </div>
        </Section>

        <Section id="defaults" title={fm(fmsg.defaults)}>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="flex flex-col gap-1 text-sm" data-field="sales_account">
              <span id="sales-account">{fm(fmsg.salesAccount)}</span>
              <AccountPicker
                accounts={accounts}
                context="sales"
                typeLabels={typeLabels}
                value={form.sales_account}
                onChange={(value) => set("sales_account", value)}
                emptyMessage={fm(fmsg.noAccount)}
                aria-labelledby="sales-account"
                invalid={Boolean(errors.sales_account)}
              />
              {errors.sales_account ? (
                <span className="text-xs text-fg-danger">{errors.sales_account}</span>
              ) : null}
            </div>
            <div className="flex flex-col gap-1 text-sm" data-field="purchase_account">
              <span id="purchase-account">{fm(fmsg.purchaseAccount)}</span>
              <AccountPicker
                accounts={accounts}
                context="purchase"
                typeLabels={typeLabels}
                value={form.purchase_account}
                onChange={(value) => set("purchase_account", value)}
                emptyMessage={fm(fmsg.noAccount)}
                aria-labelledby="purchase-account"
                invalid={Boolean(errors.purchase_account)}
              />
              {errors.purchase_account ? (
                <span className="text-xs text-fg-danger">{errors.purchase_account}</span>
              ) : null}
            </div>
          </div>
        </Section>

        <div className="flex items-center gap-3">
          <Button type="submit" variant="primary" disabled={busy}>
            {fm(fmsg.save)}
          </Button>
          <p role="status" className="text-sm text-fg-muted">
            {status}
          </p>
        </div>
      </form>
      {merging && id ? (
        <MergeDialog
          org={org}
          survivorId={id}
          mergedId={merging}
          onClose={() => setMerging(null)}
          onMerged={(survivor, message) => {
            setMerging(null);
            setContact(survivor);
            setForm(fromDetail(survivor));
            setStatus(message);
          }}
        />
      ) : null}
    </div>
  );
}
