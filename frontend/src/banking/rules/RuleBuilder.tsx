"use client";

/**
 * Rule builder (F-04-T11): the rule's name and type, the sentence-style conditions
 * (``ConditionBuilder``), then what it does — contact strategy, reference template, the other
 * bank account of a transfer, the bank accounts it runs on, auto-apply (off by default) and
 * on/off, and (F-04-T12) the allocation grid. Save is disabled until the rule is complete — for
 * spend and receive rules until the allocation percentages total 100 %; a refusal from the server is shown with
 * the part at fault. The type of a saved rule is fixed.
 */
import { Button, Checkbox, INPUT_BASE, Input, Switch } from "@numo9/ui";
import Link from "next/link";
import { useEffect, useId, useMemo, useState, type FormEvent } from "react";

import { accountsApi, type Account } from "@/accounts/api";
import { contactsApi, type ContactSummary } from "@/contacts/api";
import { useFormatMessage } from "@/i18n";
import { taxApi, type TaxCode } from "@/tax/api";

import { bankingApi, type BankAccount } from "../api";
import {
  RULE_TYPES,
  rulesApi,
  rulesUrl,
  type BankRule,
  type ContactStrategy,
  type RuleRefusal,
  type RuleType,
} from "./api";
import { AllocationGrid, allocationsValid } from "./AllocationGrid";
import { builder } from "./builderMessages";
import { ConditionBuilder, conditionComplete } from "./ConditionBuilder";
import { draftOf, newDraft, toInput, type RuleDraft } from "./draft";
import { m, typeLabels } from "./messages";

export interface RuleBuilderProps {
  org: string;
  /** The saved rule being edited (absent for a new rule). */
  rule?: BankRule;
  /** A new rule's starting point (type from the list, pre-fill from a statement line). */
  initial?: RuleDraft;
  /** Where to go after saving (default: the rules list of the rule's type). */
  navigate?: (href: string) => void;
}

const SELECT = INPUT_BASE;
const TOKENS = "{payee}, {description}, {reference}, {date}, {amount}";

export function ruleComplete(draft: RuleDraft): boolean {
  if (!draft.name.trim() || draft.conditions.length === 0) return false;
  if (!draft.conditions.every(conditionComplete)) return false;
  if (draft.contact_strategy === "fixed" && !draft.contact) return false;
  if (draft.type === "transfer") return Boolean(draft.transfer_account);
  return allocationsValid(draft.allocations);
}

export function RuleBuilder({ org, rule, initial, navigate }: RuleBuilderProps) {
  const fm = useFormatMessage();
  const id = useId();
  const [draft, setDraft] = useState<RuleDraft>(() =>
    rule ? draftOf(rule) : (initial ?? newDraft()),
  );
  const [banks, setBanks] = useState<BankAccount[]>([]);
  const [contacts, setContacts] = useState<ContactSummary[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [taxCodes, setTaxCodes] = useState<TaxCode[]>([]);
  const [busy, setBusy] = useState(false);
  const [refusal, setRefusal] = useState<RuleRefusal | null>(null);

  useEffect(() => {
    bankingApi
      .accounts(org, "active")
      .then((result) => setBanks(result.status === 200 ? result.body.results : []))
      .catch(() => setBanks([]));
    contactsApi
      .list(org, { status: "active" })
      .then((result) => setContacts(result.status === 200 ? result.body.results : []))
      .catch(() => setContacts([]));
    accountsApi
      .list(org, "active")
      .then((result) => setAccounts(result.status === 200 ? result.body.results : []))
      .catch(() => setAccounts([]));
    taxApi
      .codes(org)
      .then((result) => setTaxCodes(result.status === 200 ? result.body.results : []))
      .catch(() => setTaxCodes([]));
  }, [org]);

  const complete = useMemo(() => ruleComplete(draft), [draft]);

  function change(changes: Partial<RuleDraft>) {
    setDraft((current) => ({ ...current, ...changes }));
  }

  function setType(type: RuleType) {
    setDraft((current) => ({
      ...newDraft(type),
      ...current,
      type,
      allocations:
        type === "transfer"
          ? []
          : current.allocations.length
            ? current.allocations
            : newDraft(type).allocations,
    }));
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!complete || busy) return;
    setBusy(true);
    setRefusal(null);
    const body = toInput(draft);
    const result = await (
      rule ? rulesApi.update(org, rule.id, body) : rulesApi.create(org, body)
    ).catch(() => null);
    setBusy(false);
    if (result && (result.status === 200 || result.status === 201)) {
      const href = rulesUrl(org, draft.type);
      if (navigate) navigate(href);
      else window.location.assign(href);
      return;
    }
    setRefusal(
      result && typeof result.body === "object" && result.body
        ? (result.body as RuleRefusal)
        : { detail: fm(builder.saveFailed) },
    );
  }

  return (
    <form className="flex max-w-4xl flex-col gap-8" onSubmit={(e) => void save(e)} noValidate>
      <div className="flex flex-col gap-1">
        <Link href={rulesUrl(org, draft.type)} className="text-sm text-fg-link underline">
          {fm(m.back)}
        </Link>
        <h1 className="text-2xl font-bold text-fg">
          {rule ? fm(builder.editTitle, { name: rule.name }) : fm(builder.newTitle)}
        </h1>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm font-semibold text-fg">
          {fm(builder.name)}
          <Input value={draft.name} onChange={(e) => change({ name: e.target.value })} required />
        </label>
        <label className="flex flex-col gap-1 text-sm font-semibold text-fg">
          {fm(builder.type)}
          <select
            className={SELECT}
            value={draft.type}
            disabled={Boolean(rule)}
            aria-describedby={rule ? `${id}-type-fixed` : undefined}
            onChange={(e) => setType(e.target.value as RuleType)}
          >
            {RULE_TYPES.map((t) => (
              <option key={t} value={t}>
                {fm(typeLabels[t])}
              </option>
            ))}
          </select>
          {rule ? (
            <span id={`${id}-type-fixed`} className="text-xs font-normal text-fg-muted">
              {fm(builder.typeFixed)}
            </span>
          ) : null}
        </label>
      </div>

      <ConditionBuilder
        conditions={draft.conditions}
        matchMode={draft.match_mode}
        onChange={(conditions) => change({ conditions })}
        onMatchModeChange={(match_mode) => change({ match_mode })}
      />

      {draft.type !== "transfer" ? (
        <AllocationGrid
          type={draft.type}
          rows={draft.allocations}
          accounts={accounts}
          taxCodes={taxCodes}
          onChange={(allocations) => change({ allocations })}
        />
      ) : null}

      <section className="flex flex-col gap-4" aria-labelledby={`${id}-then`}>
        <h2 id={`${id}-then`} className="text-lg font-semibold text-fg">
          {fm(builder.options)}
        </h2>
        {draft.type === "transfer" ? (
          <label className="flex flex-col gap-1 text-sm font-semibold text-fg">
            {fm(builder.transferAccount)}
            <select
              className={SELECT}
              value={draft.transfer_account ?? ""}
              onChange={(e) => change({ transfer_account: e.target.value || null })}
            >
              <option value="" />
              {banks.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.display_name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm font-semibold text-fg">
            {fm(builder.contactStrategy)}
            <select
              className={SELECT}
              value={draft.contact_strategy}
              onChange={(e) => change({ contact_strategy: e.target.value as ContactStrategy })}
            >
              <option value="none">{fm(builder.contactNone)}</option>
              <option value="fixed">{fm(builder.contactFixed)}</option>
              <option value="match_payee">{fm(builder.contactPayee)}</option>
            </select>
          </label>
          {draft.contact_strategy === "fixed" ? (
            <label className="flex flex-col gap-1 text-sm font-semibold text-fg">
              {fm(builder.contactPick)}
              <select
                className={SELECT}
                value={draft.contact ?? ""}
                onChange={(e) => change({ contact: e.target.value || null })}
              >
                <option value="" />
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.display_name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
        <label className="flex flex-col gap-1 text-sm font-semibold text-fg">
          {fm(builder.reference)}
          <Input
            value={draft.reference_template}
            aria-describedby={`${id}-tokens`}
            onChange={(e) => change({ reference_template: e.target.value })}
          />
          <span id={`${id}-tokens`} className="text-xs font-normal text-fg-muted">
            {fm(builder.referenceHint, { tokens: TOKENS })}
          </span>
        </label>
        {banks.length ? (
          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm font-semibold text-fg">{fm(builder.scope)}</legend>
            <p className="text-xs text-fg-muted">{fm(builder.scopeHint)}</p>
            {banks.map((b) => (
              <Checkbox
                key={b.id}
                label={b.display_name}
                checked={draft.scope_accounts.includes(b.id)}
                onCheckedChange={(checked) =>
                  change({
                    scope_accounts: checked
                      ? [...draft.scope_accounts, b.id]
                      : draft.scope_accounts.filter((x) => x !== b.id),
                  })
                }
              />
            ))}
          </fieldset>
        ) : null}
        <Switch
          label={fm(builder.autoApply)}
          description={fm(builder.autoApplyHint)}
          checked={draft.auto_apply}
          onCheckedChange={(auto_apply) => change({ auto_apply })}
        />
        <Switch
          label={fm(builder.active)}
          checked={draft.active}
          onCheckedChange={(active) => change({ active })}
        />
      </section>

      {refusal ? (
        <div role="alert" className="rounded-lg border border-border bg-surface-danger-subtle p-4">
          <p className="font-semibold text-fg">{fm(builder.saveFailed)}</p>
          {refusal.detail ? <p className="text-sm text-fg">{refusal.detail}</p> : null}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" variant="primary" disabled={!complete || busy}>
          {busy ? fm(builder.saving) : fm(builder.save)}
        </Button>
        <Link href={rulesUrl(org, draft.type)} className="text-sm font-semibold text-fg underline">
          {fm(builder.cancel)}
        </Link>
        {!complete ? <p className="text-sm text-fg-muted">{fm(builder.incomplete)}</p> : null}
      </div>
    </form>
  );
}
