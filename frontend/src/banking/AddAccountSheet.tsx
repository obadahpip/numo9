"use client";

/**
 * Add a bank account (F-01-T09, wireframe 39): a side-sheet with four fields — type (one choice
 * with a plain-language line under it), name, institution (Canadian bank list, free text allowed)
 * and currency — plus the optional last 4 digits. Creating it creates its ledger account in the
 * same step (F-01-T03); the server's refusal ("There's already an account called …") is shown on
 * the form. On success the sheet closes and the banking page shows "… is ready." with
 * **Record a transaction**.
 */
import { Button, Drawer, Input, RadioGroup } from "@numo9/ui";
import { useEffect, useId, useState, type FormEvent } from "react";

import { useFormatMessage } from "@/i18n";

import { BANK_ACCOUNT_TYPES, bankingApi, type BankAccount, type BankAccountType } from "./api";
import { CANADIAN_INSTITUTIONS } from "./institutions";
import { sheet, typeHelp, typeLabels } from "./messages";

export interface AddAccountSheetProps {
  org: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (account: BankAccount) => void;
}

const CURRENCIES = ["CAD", "USD"];

export function AddAccountSheet({ org, open, onOpenChange, onCreated }: AddAccountSheetProps) {
  const fm = useFormatMessage();
  const ids = useId();
  const [type, setType] = useState<BankAccountType>("chequing");
  const [name, setName] = useState("");
  const [institution, setInstitution] = useState("");
  const [currency, setCurrency] = useState("CAD");
  const [last4, setLast4] = useState("");
  const [errors, setErrors] = useState<{ name?: string; last4?: string; form?: string }>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setType("chequing");
    setName("");
    setInstitution("");
    setCurrency("CAD");
    setLast4("");
    setErrors({});
  }, [open]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: typeof errors = {};
    if (!name.trim()) found.name = fm(sheet.nameRequired);
    if (last4 && !/^\d{4}$/.test(last4)) found.last4 = fm(sheet.last4Invalid);
    setErrors(found);
    if (Object.keys(found).length) return;
    setSaving(true);
    const result = await bankingApi.create(org, {
      type,
      display_name: name.trim(),
      institution: institution.trim(),
      currency,
      account_last4: last4,
    });
    setSaving(false);
    if (result.status === 201) {
      onCreated(result.body);
      onOpenChange(false);
      return;
    }
    const detail = result.body?.detail;
    if (result.body?.code === "banking.account.name_taken" && detail) setErrors({ name: detail });
    else setErrors({ form: detail || fm(sheet.failed) });
  };

  const formId = `${ids}-form`;
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={fm(sheet.title)}
      description={fm(sheet.description)}
      closeLabel={fm(sheet.close)}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            {fm(sheet.cancel)}
          </Button>
          <Button variant="primary" type="submit" form={formId} disabled={saving}>
            {fm(saving ? sheet.saving : sheet.submit)}
          </Button>
        </>
      }
    >
      <form id={formId} className="flex flex-col gap-5" onSubmit={(e) => void submit(e)} noValidate>
        {errors.form ? (
          <p role="alert" className="text-sm text-fg-danger">
            {errors.form}
          </p>
        ) : null}
        <fieldset className="flex flex-col gap-2">
          <legend id={`${ids}-type`} className="text-sm font-medium text-fg">
            {fm(sheet.type)}
          </legend>
          <RadioGroup
            aria-labelledby={`${ids}-type`}
            value={type}
            onValueChange={(value) => setType(value as BankAccountType)}
            options={BANK_ACCOUNT_TYPES.map((value) => ({
              value,
              label: fm(typeLabels[value]),
            }))}
            className="grid grid-cols-2 gap-2"
          />
          <p className="text-sm text-fg-muted" data-type-help="">
            {fm(typeHelp[type])}
          </p>
        </fieldset>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${ids}-name`} className="text-sm font-medium text-fg">
            {fm(sheet.name)}
          </label>
          <Input
            id={`${ids}-name`}
            value={name}
            required
            maxLength={120}
            placeholder={fm(sheet.namePlaceholder)}
            invalid={Boolean(errors.name)}
            aria-describedby={errors.name ? `${ids}-name-error` : undefined}
            onChange={(e) => setName(e.target.value)}
          />
          {errors.name ? (
            <p id={`${ids}-name-error`} className="text-sm text-fg-danger">
              {errors.name}
            </p>
          ) : null}
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${ids}-institution`} className="text-sm font-medium text-fg">
            {fm(sheet.institution)}
          </label>
          <Input
            id={`${ids}-institution`}
            value={institution}
            maxLength={120}
            list={`${ids}-institutions`}
            aria-describedby={`${ids}-institution-hint`}
            onChange={(e) => setInstitution(e.target.value)}
          />
          <datalist id={`${ids}-institutions`}>
            {CANADIAN_INSTITUTIONS.map((bank) => (
              <option key={bank} value={bank} />
            ))}
          </datalist>
          <p id={`${ids}-institution-hint`} className="text-xs text-fg-muted">
            {fm(sheet.institutionHint)}
          </p>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor={`${ids}-currency`} className="text-sm font-medium text-fg">
              {fm(sheet.currency)}
            </label>
            <select
              id={`${ids}-currency`}
              value={currency}
              aria-describedby={`${ids}-currency-hint`}
              onChange={(e) => setCurrency(e.target.value)}
              className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-fg"
            >
              {CURRENCIES.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
            <p id={`${ids}-currency-hint`} className="text-xs text-fg-muted">
              {fm(sheet.currencyHint)}
            </p>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor={`${ids}-last4`} className="text-sm font-medium text-fg">
              {fm(sheet.last4)}
            </label>
            <Input
              id={`${ids}-last4`}
              value={last4}
              inputMode="numeric"
              maxLength={4}
              invalid={Boolean(errors.last4)}
              aria-describedby={`${ids}-last4-hint`}
              onChange={(e) => setLast4(e.target.value.replace(/\D/g, ""))}
            />
            <p id={`${ids}-last4-hint`} className="text-xs text-fg-muted">
              {errors.last4 ?? fm(sheet.last4Hint)}
            </p>
          </div>
        </div>
      </form>
    </Drawer>
  );
}
