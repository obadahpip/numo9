"use client";

/**
 * Account drawer (C-01-T12): an account's details, balance in each book, posting rules (contact,
 * tracking, attachment required), GIFI mapping with search by number or description, the default
 * tax key, and archive / restore (the server's reason shown when refused).
 */
import { Button, Checkbox, Drawer, formatMoney, Input, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { accountsApi, refusal, type Account, type AccountChanges, type GifiOption } from "./api";
import { m } from "./messages";

export function AccountDrawer({
  org,
  account,
  onClose,
  onChange,
}: {
  org: string;
  account: Account;
  onClose: () => void;
  onChange: (account: Account) => void;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const id = useId();
  const [name, setName] = useState(account.name);
  const [description, setDescription] = useState(account.description);
  const [flags, setFlags] = useState({
    require_contact: account.require_contact,
    require_tracking: account.require_tracking,
    require_attachment: account.require_attachment,
  });
  const [gifi, setGifi] = useState(account.gifi);
  const [taxKey, setTaxKey] = useState(account.default_tax_key);
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<GifiOption[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const text = query.trim();
    if (!text) {
      setOptions([]);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      void accountsApi.gifi(org, text, account.type).then((result) => {
        if (!cancelled && result.status === 200) setOptions(result.body.results.slice(0, 8));
      });
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, org, account.type]);

  const done = (result: Awaited<ReturnType<typeof accountsApi.update>>) => {
    setBusy(false);
    if (result.status === 200) {
      setError("");
      setStatus(fm(m.saved));
      onChange(result.body);
    } else {
      setStatus("");
      setError(refusal(result) ?? fm(m.saveFailed));
    }
  };

  const save = async () => {
    const changes: AccountChanges = {
      name,
      description,
      ...flags,
      default_tax_key: taxKey,
      gifi: gifi?.code ?? null,
    };
    setBusy(true);
    done(await accountsApi.update(org, account.id, changes));
  };

  const archived = account.status === "archived";
  const money = (amount: string) => formatMoney(amount, { locale });

  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={fm(m.drawerTitle, { code: account.code, name: account.name })}
      description={fm(m.typeLine, { type: account.type_label, subtype: account.subtype_label })}
      closeLabel={fm(m.close)}
      size="md"
      footer={
        <>
          <Button
            variant={archived ? "secondary" : "danger"}
            disabled={busy}
            onClick={() => {
              setBusy(true);
              void (
                archived
                  ? accountsApi.restore(org, account.id)
                  : accountsApi.archive(org, account.id)
              ).then(done);
            }}
          >
            {fm(archived ? m.restore : m.archive)}
          </Button>
          <Button variant="primary" disabled={busy} onClick={() => void save()}>
            {fm(m.save)}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-6">
        <section className="flex flex-col gap-3" aria-labelledby={`${id}-details`}>
          <h3 id={`${id}-details`} className="text-sm font-semibold">
            {fm(m.details)}
          </h3>
          <label className="flex flex-col gap-1 text-sm">
            {fm(m.name)}
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            {fm(m.description)}
            <Input value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
        </section>

        <section aria-labelledby={`${id}-balance`}>
          <h3 id={`${id}-balance`} className="text-sm font-semibold">
            {fm(m.balances)}
          </h3>
          <dl className="mt-2 grid grid-cols-2 gap-2 text-sm">
            <dt className="text-fg-muted">{fm(m.accountingBook)}</dt>
            <dd className="text-end tabular-nums" data-balance="accounting">
              {money(account.balance.accounting)}
            </dd>
            <dt className="text-fg-muted">{fm(m.taxBook)}</dt>
            <dd className="text-end tabular-nums" data-balance="tax">
              {money(account.balance.tax)}
            </dd>
          </dl>
        </section>

        <section className="flex flex-col gap-2" aria-labelledby={`${id}-rules`}>
          <h3 id={`${id}-rules`} className="text-sm font-semibold">
            {fm(m.rules)}
          </h3>
          {(
            [
              ["require_contact", m.requireContact],
              ["require_tracking", m.requireTracking],
              ["require_attachment", m.requireAttachment],
            ] as const
          ).map(([key, label]) => (
            <Checkbox
              key={key}
              label={fm(label)}
              checked={flags[key]}
              onCheckedChange={(checked) =>
                setFlags((current) => ({ ...current, [key]: checked === true }))
              }
            />
          ))}
        </section>

        <section className="flex flex-col gap-2" aria-labelledby={`${id}-gifi`}>
          <h3 id={`${id}-gifi`} className="text-sm font-semibold">
            {fm(m.gifi)}
          </h3>
          <p className="text-sm" data-gifi-current="">
            {gifi
              ? fm(m.gifiCurrent, { code: gifi.code, description: gifi.description })
              : fm(m.gifiNone)}
          </p>
          <label className="flex flex-col gap-1 text-sm">
            {fm(m.gifiSearch)}
            <Input type="search" value={query} onChange={(event) => setQuery(event.target.value)} />
          </label>
          {options.length > 0 ? (
            <ul className="flex flex-col gap-1">
              {options.map((option) => (
                <li key={option.code}>
                  <button
                    type="button"
                    className="w-full rounded-sm px-2 py-1 text-start text-sm hover:bg-surface-muted"
                    onClick={() => {
                      setGifi({ code: option.code, description: option.description });
                      setQuery("");
                    }}
                  >
                    {fm(m.gifiPick, { code: option.code, description: option.description })}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </section>

        <label className="flex flex-col gap-1 text-sm">
          {fm(m.taxDefault)}
          <Input value={taxKey} onChange={(event) => setTaxKey(event.target.value)} />
          <span className="text-xs text-fg-muted">{fm(m.taxDefaultHint)}</span>
        </label>

        {error ? (
          <p role="alert" className="text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
        <p role="status" className="text-sm text-fg-muted">
          {status}
        </p>
      </div>
    </Drawer>
  );
}
