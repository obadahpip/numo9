"use client";

import {
  ErrorState,
  Field,
  Form,
  LoadingRegion,
  PostalCodeInput,
  ProvincePicker,
  SelectField,
  SkeletonText,
  TextField,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import { z } from "zod";

import { useFormLabels } from "@/components/useFormLabels";
import { defineMessages, useFormatMessage } from "@/i18n";

import { getSettings, saveSettings, type FieldErrors, type OrganisationSettings } from "./api";

const m = defineMessages({
  title: { id: "settings.general.title", defaultMessage: "General", description: "Page heading" },
  intro: {
    id: "settings.general.intro",
    defaultMessage:
      "Your organisation's names, address and fiscal year, as they appear on documents and in Numo9.",
    description: "Text under the heading",
  },
  identity: {
    id: "settings.general.identity",
    defaultMessage: "Organisation",
    description: "Section",
  },
  address: {
    id: "settings.general.address",
    defaultMessage: "Mailing address",
    description: "Section",
  },
  contact: { id: "settings.general.contact", defaultMessage: "Contact", description: "Section" },
  year: {
    id: "settings.general.year",
    defaultMessage: "Fiscal year and time",
    description: "Section",
  },
  displayName: {
    id: "settings.general.displayName",
    defaultMessage: "Display name",
    description: "Field",
  },
  legalName: {
    id: "settings.general.legalName",
    defaultMessage: "Legal name",
    description: "Field",
  },
  legalNameHint: {
    id: "settings.general.legalNameHint",
    defaultMessage: "As registered, e.g. Refined Interiors Inc. — not a number.",
    description: "Hint",
  },
  industry: { id: "settings.general.industry", defaultMessage: "Industry", description: "Field" },
  structure: {
    id: "settings.general.structure",
    defaultMessage: "Business structure",
    description: "Field",
  },
  line1: {
    id: "settings.general.line1",
    defaultMessage: "Street address or PO box",
    description: "Field",
  },
  line2: { id: "settings.general.line2", defaultMessage: "Address line 2", description: "Field" },
  city: { id: "settings.general.city", defaultMessage: "City", description: "Field" },
  province: {
    id: "settings.general.province",
    defaultMessage: "Province or territory",
    description: "Field",
  },
  provinces: {
    id: "settings.general.provinces",
    defaultMessage: "Provinces",
    description: "Group",
  },
  territories: {
    id: "settings.general.territories",
    defaultMessage: "Territories",
    description: "Group",
  },
  postalCode: {
    id: "settings.general.postalCode",
    defaultMessage: "Postal code",
    description: "Field",
  },
  postalCodeHint: {
    id: "settings.general.postalCodeHint",
    defaultMessage: "Like A1A 1A1",
    description: "Hint",
  },
  postalCodeInvalid: {
    id: "settings.general.postalCodeInvalid",
    defaultMessage: "Enter a Canadian postal code like A1A 1A1.",
    description: "Error",
  },
  phone: { id: "settings.general.phone", defaultMessage: "Telephone", description: "Field" },
  email: { id: "settings.general.email", defaultMessage: "Email", description: "Field" },
  emailInvalid: {
    id: "settings.general.emailInvalid",
    defaultMessage: "Enter an email address like books@refined.ca.",
    description: "Error",
  },
  website: { id: "settings.general.website", defaultMessage: "Website", description: "Field" },
  fyeMonth: {
    id: "settings.general.fyeMonth",
    defaultMessage: "Fiscal year end: month",
    description: "Field",
  },
  fyeDay: {
    id: "settings.general.fyeDay",
    defaultMessage: "Fiscal year end: day",
    description: "Field",
  },
  fyeDayInvalid: {
    id: "settings.general.fyeDayInvalid",
    defaultMessage: "Enter a day from 1 to 31.",
    description: "Error",
  },
  timeZone: { id: "settings.general.timeZone", defaultMessage: "Time zone", description: "Field" },
  currency: {
    id: "settings.general.currency",
    defaultMessage: "Base currency: {currency} (can't change)",
    description: "Read-only base currency",
  },
  required: {
    id: "settings.general.required",
    defaultMessage: "Enter the display name.",
    description: "Error",
  },
  saved: { id: "settings.general.saved", defaultMessage: "Settings saved.", description: "Status" },
  saveFailed: {
    id: "settings.general.saveFailed",
    defaultMessage: "The settings couldn't be saved. Try again.",
    description: "Status",
  },
  loading: {
    id: "settings.general.loading",
    defaultMessage: "Loading the settings…",
    description: "Loading",
  },
  loadFailed: {
    id: "settings.general.loadFailed",
    defaultMessage: "The settings couldn't be loaded",
    description: "Error",
  },
  loadFailedBody: {
    id: "settings.general.loadFailedBody",
    defaultMessage: "Verify your connection, then try again.",
    description: "Error body",
  },
  retry: { id: "settings.general.retry", defaultMessage: "Try again", description: "Retry" },
  structureOption: {
    id: "settings.general.structureOption",
    defaultMessage:
      "{value, select, sole_proprietorship {Sole proprietorship} partnership {Partnership} corporation {Corporation} non_profit {Non-profit organisation} charity {Registered charity} cooperative {Co-operative} trust {Trust} other {Other}}",
    description: "Business structure option",
  },
});

const TIME_ZONES = [
  "America/St_Johns",
  "America/Halifax",
  "America/Moncton",
  "America/Toronto",
  "America/Winnipeg",
  "America/Regina",
  "America/Edmonton",
  "America/Vancouver",
  "America/Whitehorse",
  "America/Yellowknife",
  "America/Iqaluit",
];
const STRUCTURES = [
  "sole_proprietorship",
  "partnership",
  "corporation",
  "non_profit",
  "charity",
  "cooperative",
  "trust",
  "other",
];
const POSTAL = /^[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z] ?\d[ABCEGHJ-NPRSTV-Z]\d$/i;

type Values = {
  display_name: string;
  legal_name: string;
  industry: string;
  structure: string;
  mailing_line1: string;
  mailing_line2: string;
  mailing_city: string;
  mailing_province: string;
  mailing_postal_code: string;
  phone: string;
  email: string;
  website: string;
  fye_month: string;
  fye_day: string;
  time_zone: string;
};

const FIELDS: (keyof Values)[] = [
  "display_name",
  "legal_name",
  "industry",
  "structure",
  "mailing_line1",
  "mailing_line2",
  "mailing_city",
  "mailing_province",
  "mailing_postal_code",
  "phone",
  "email",
  "website",
  "fye_month",
  "fye_day",
  "time_zone",
];

/**
 * Settings → General (A-05-T11): the organisation's names, Canadian mailing address (Province
 * picker, Postal code mask A1A 1A1), contact, fiscal year end and time zone. Client rules show
 * inline; the server's rules (numeric-only legal name, postal code ↔ province…) come back on the
 * field. Sticky save bar and unsaved-changes guard from the form kit.
 */
export function GeneralSettingsScreen({ org }: Readonly<{ org: string }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as "en-CA" | "fr-CA";
  const labels = useFormLabels();
  const [data, setData] = useState<OrganisationSettings | null>(null);
  const [failed, setFailed] = useState(false);
  const [status, setStatus] = useState("");

  const load = useCallback(async () => {
    setFailed(false);
    const answer = await getSettings(org);
    if (answer.status === 200 && "display_name" in answer.body) setData(answer.body);
    else setFailed(true);
  }, [org]);
  useEffect(() => {
    void load();
  }, [load]);

  const schema = useMemo(
    () =>
      z.object({
        display_name: z.string().trim().min(1, fm(m.required)),
        legal_name: z.string(),
        industry: z.string(),
        structure: z.string(),
        mailing_line1: z.string(),
        mailing_line2: z.string(),
        mailing_city: z.string(),
        mailing_province: z.string(),
        mailing_postal_code: z
          .string()
          .refine((v) => v === "" || POSTAL.test(v), fm(m.postalCodeInvalid)),
        phone: z.string(),
        email: z
          .string()
          .refine((v) => v === "" || /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v), fm(m.emailInvalid)),
        website: z.string(),
        fye_month: z.string(),
        fye_day: z
          .string()
          .refine((v) => /^\d{1,2}$/.test(v) && +v >= 1 && +v <= 31, fm(m.fyeDayInvalid)),
        time_zone: z.string(),
      }),
    [fm],
  );

  const header = (
    <header className="flex flex-col gap-2">
      <h1 className="text-2xl font-semibold">{fm(m.title)}</h1>
      <p className="text-fg-muted">{fm(m.intro)}</p>
    </header>
  );
  if (failed || !data)
    return (
      <div className="flex max-w-3xl flex-col gap-6">
        {header}
        {failed ? (
          <ErrorState
            title={fm(m.loadFailed)}
            body={fm(m.loadFailedBody)}
            retryLabel={fm(m.retry)}
            onRetry={() => void load()}
          />
        ) : (
          <LoadingRegion label={fm(m.loading)}>
            <SkeletonText lines={10} />
          </LoadingRegion>
        )}
      </div>
    );

  const defaults = Object.fromEntries(FIELDS.map((f) => [f, String(data[f] ?? "")])) as Values;
  const months = Array.from({ length: 12 }, (_, i) => ({
    value: String(i + 1),
    label: new Intl.DateTimeFormat(locale, { month: "long", timeZone: "UTC" }).format(
      new Date(Date.UTC(2026, i, 1)),
    ),
  }));

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      {header}
      <p role="status" aria-live="polite" className="text-fg-muted" data-settings-status>
        {status}
      </p>
      <Form<z.ZodType<Values, Values>>
        schema={schema as unknown as z.ZodType<Values, Values>}
        defaultValues={defaults}
        labels={labels}
        aria-label={fm(m.title)}
        className="flex flex-col gap-8"
        onSubmit={async (values, form) => {
          const change = {
            ...values,
            fye_month: Number(values.fye_month),
            fye_day: Number(values.fye_day),
          };
          const answer = await saveSettings(
            org,
            change as unknown as Partial<OrganisationSettings>,
          );
          if (answer.status === 200 && "display_name" in answer.body) {
            setData(answer.body as OrganisationSettings);
            form.reset(
              Object.fromEntries(
                FIELDS.map((f) => [f, String((answer.body as OrganisationSettings)[f] ?? "")]),
              ) as Values,
            );
            setStatus(fm(m.saved));
          } else if (answer.status === 400) {
            for (const [field, messages] of Object.entries(answer.body as FieldErrors)) {
              if (FIELDS.includes(field as keyof Values) && Array.isArray(messages) && messages[0])
                form.setError(field as keyof Values, {
                  type: "server",
                  message: String(messages[0]),
                });
            }
            setStatus("");
          } else setStatus(fm(m.saveFailed));
        }}
      >
        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="mb-2 text-lg font-semibold">{fm(m.identity)}</legend>
          <TextField name="display_name" label={fm(m.displayName)} required />
          <TextField name="legal_name" label={fm(m.legalName)} hint={fm(m.legalNameHint)} />
          <TextField name="industry" label={fm(m.industry)} />
          <SelectField
            name="structure"
            label={fm(m.structure)}
            options={STRUCTURES.map((value) => ({
              value,
              label: fm(m.structureOption, { value }),
            }))}
          />
        </fieldset>
        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="mb-2 text-lg font-semibold">{fm(m.address)}</legend>
          <TextField
            name="mailing_line1"
            label={fm(m.line1)}
            className="grid gap-1 sm:col-span-2"
            autoComplete="address-line1"
          />
          <TextField
            name="mailing_line2"
            label={fm(m.line2)}
            className="grid gap-1 sm:col-span-2"
            autoComplete="address-line2"
          />
          <TextField name="mailing_city" label={fm(m.city)} autoComplete="address-level2" />
          <Field name="mailing_province" label={fm(m.province)}>
            {({ id, invalid, describedBy, field }) => (
              <ProvincePicker
                id={id}
                locale={locale}
                groupLabels={{ provinces: fm(m.provinces), territories: fm(m.territories) }}
                value={(field.value as string) || undefined}
                onValueChange={(v) => {
                  field.onChange(v);
                  field.onBlur();
                }}
                invalid={invalid}
                aria-describedby={describedBy}
              />
            )}
          </Field>
          <Field name="mailing_postal_code" label={fm(m.postalCode)} hint={fm(m.postalCodeHint)}>
            {({ id, invalid, describedBy, field }) => (
              <PostalCodeInput
                id={id}
                value={(field.value as string) ?? ""}
                onChange={field.onChange}
                onBlur={field.onBlur}
                invalid={invalid}
                aria-describedby={describedBy}
                autoComplete="postal-code"
              />
            )}
          </Field>
        </fieldset>
        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="mb-2 text-lg font-semibold">{fm(m.contact)}</legend>
          <TextField name="phone" label={fm(m.phone)} type="tel" autoComplete="tel" />
          <TextField name="email" label={fm(m.email)} type="email" autoComplete="email" />
          <TextField
            name="website"
            label={fm(m.website)}
            type="url"
            className="grid gap-1 sm:col-span-2"
          />
        </fieldset>
        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="mb-2 text-lg font-semibold">{fm(m.year)}</legend>
          <SelectField name="fye_month" label={fm(m.fyeMonth)} options={months} />
          <TextField name="fye_day" label={fm(m.fyeDay)} inputMode="numeric" />
          <SelectField
            name="time_zone"
            label={fm(m.timeZone)}
            options={TIME_ZONES.map((z) => ({
              value: z,
              label: z.replace("America/", "").replace("_", " "),
            }))}
          />
          <p className="self-end text-fg-muted">
            {fm(m.currency, { currency: data.base_currency })}
          </p>
        </fieldset>
      </Form>
    </div>
  );
}
