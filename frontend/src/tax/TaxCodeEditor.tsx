"use client";

/**
 * Tax code editor (G-01-T13, wireframe 44): header fields (code, name, side, type, province), the
 * component builder (pick components in force, a recoverable % per component on purchases), the
 * claimable ITC % of the code, the effective-from date and a live calculation example computed
 * with the client mirror of the server's calculator — "100.00 → GST 5.00 + PST 7.00 = 112.00;
 * recoverable 5.00". A new code is created as version 1; saving an existing code creates the next
 * version from the date (posted lines keep theirs, G-01-T10).
 */
import { Button, Input, PROVINCES, Switch, formatMoney, type AppLocale } from "@numo9/ui";
import Link from "next/link";
import { useLocale } from "next-intl";
import { useEffect, useId, useMemo, useState, type FormEvent, type ReactNode } from "react";

import { useFormatMessage } from "@/i18n";

import { taxApi, type TaxCode, type TaxCodeType, type TaxComponent, type TaxSide } from "./api";
import { calculateTax } from "./calculator";
import { ed, m, typeLabels } from "./messages";

const TYPES: TaxCodeType[] = ["taxable", "zero_rated", "exempt", "out_of_scope"];

interface Row {
  component: string;
  recoverable: string;
}

export interface TaxCodeEditorProps {
  org: string;
  /** The code version to edit; absent for a new code. */
  code?: TaxCode | null;
  side?: TaxSide;
  /** Called after a successful save with the saved version. */
  onSaved?: (code: TaxCode) => void;
  /** Today in the organisation (the default effective date of a new version). */
  today?: string;
}

export function TaxCodeEditor({
  org,
  code = null,
  side: initialSide = "sales",
  onSaved,
  today = new Date().toISOString().slice(0, 10),
}: TaxCodeEditorProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const editing = code !== null;
  const [key, setKey] = useState(code?.code ?? "");
  const [name, setName] = useState(code?.name ?? "");
  const [side, setSide] = useState<TaxSide>(code?.side ?? initialSide);
  const [type, setType] = useState<TaxCodeType>(code?.type ?? "taxable");
  const [province, setProvince] = useState(code?.province ?? "");
  const [from, setFrom] = useState(today);
  const [claimable, setClaimable] = useState(code?.itc_restriction_pct ?? "");
  const [rows, setRows] = useState<Row[]>(
    code?.components.map((c) => ({ component: c.id, recoverable: c.recoverable_pct ?? "" })) ?? [],
  );
  const [available, setAvailable] = useState<TaxComponent[]>([]);
  const [amount, setAmount] = useState("100.00");
  const [inclusive, setInclusive] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void taxApi.components(org).then((result) => {
      if (!cancelled && result.status === 200 && Array.isArray(result.body?.results)) {
        setAvailable(result.body.results);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [org]);

  const purchase = side === "purchase";
  const noTax = type === "exempt" || type === "out_of_scope";
  const choices = available.filter((c) => c.side === "both" || c.side === side);
  const picked = rows
    .map((row) => ({ row, component: available.find((c) => c.id === row.component) }))
    .filter((item): item is { row: Row; component: TaxComponent } => Boolean(item.component));

  const example = useMemo(() => {
    const parts = noTax
      ? []
      : picked.map(({ row, component }) => ({
          key: component.key,
          name: component.name,
          rate: component.rate,
          claimablePct: !component.recoverable ? 0 : row.recoverable || claimable || "100",
        }));
    try {
      return { parts, out: calculateTax(parts, amount || "0", { inclusive, purchase }) };
    } catch {
      return null;
    }
  }, [picked, amount, inclusive, purchase, claimable, noTax]);

  const money = (value: string) => formatMoney(value, { locale, currency: "CAD" });

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (!key.trim() || !name.trim() || !from) {
      setError(fm(ed.required));
      return;
    }
    const components = noTax
      ? []
      : rows
          .filter((row) => row.component)
          .map((row) => ({
            component: row.component,
            recoverable_pct: purchase && row.recoverable ? row.recoverable : null,
          }));
    setSaving(true);
    const result = editing
      ? await taxApi.version(org, code.id, { effective_from: from, components, name: name.trim() })
      : await taxApi.create(org, {
          code: key.trim(),
          name: name.trim(),
          side,
          type,
          province,
          effective_from: from,
          itc_restriction_pct: purchase && claimable ? claimable : null,
          components,
        });
    setSaving(false);
    if (result.status === 201) {
      setStatus(fm(ed.saved, { name: result.body.name, version: result.body.version }));
      onSaved?.(result.body);
      return;
    }
    setError(result.body?.detail || fm(ed.failed));
  };

  return (
    <form
      className="flex flex-col gap-6"
      onSubmit={(e) => void submit(e)}
      noValidate
      data-tax-editor=""
    >
      <nav className="text-sm" aria-label={fm(ed.back)}>
        <Link href={`/o/${org}/settings/tax-codes`} className="underline">
          {fm(ed.back)}
        </Link>
      </nav>
      <h1 className="text-2xl font-bold text-fg">
        {editing ? fm(ed.editTitle, { name: code.name }) : fm(ed.newTitle)}
      </h1>
      <p role="status" className="text-sm text-fg">
        {status}
      </p>
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <div className="grid gap-4 md:grid-cols-3">
        <Field id={`${ids}-code`} label={fm(ed.code)} hint={fm(ed.codeHint)}>
          <Input
            id={`${ids}-code`}
            value={key}
            disabled={editing}
            onChange={(e) => setKey(e.target.value)}
            aria-describedby={`${ids}-code-hint`}
          />
        </Field>
        <Field id={`${ids}-name`} label={fm(ed.name)}>
          <Input id={`${ids}-name`} value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field id={`${ids}-side`} label={fm(ed.side)}>
          <select
            id={`${ids}-side`}
            value={side}
            disabled={editing}
            onChange={(e) => setSide(e.target.value as TaxSide)}
            className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-fg"
          >
            <option value="sales">{fm(m.sales)}</option>
            <option value="purchase">{fm(m.purchases)}</option>
          </select>
        </Field>
        <Field id={`${ids}-type`} label={fm(ed.type)}>
          <select
            id={`${ids}-type`}
            value={type}
            disabled={editing}
            onChange={(e) => setType(e.target.value as TaxCodeType)}
            className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-fg"
          >
            {TYPES.map((value) => (
              <option key={value} value={value}>
                {fm(typeLabels[value])}
              </option>
            ))}
          </select>
        </Field>
        <Field id={`${ids}-province`} label={fm(ed.province)}>
          <select
            id={`${ids}-province`}
            value={province}
            disabled={editing}
            onChange={(e) => setProvince(e.target.value)}
            className="h-10 rounded-md border border-border bg-surface px-3 text-sm text-fg"
          >
            <option value="">{fm(ed.anywhere)}</option>
            {PROVINCES.map((p) => (
              <option key={p.code} value={p.code}>
                {locale === "fr-CA" ? p.fr : p.en}
              </option>
            ))}
          </select>
        </Field>
        <Field
          id={`${ids}-from`}
          label={fm(ed.effectiveFrom)}
          hint={
            editing
              ? fm(ed.newVersionHint, { version: (code.version ?? 1) + 1, current: code.version })
              : undefined
          }
        >
          <Input
            id={`${ids}-from`}
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            aria-describedby={editing ? `${ids}-from-hint` : undefined}
          />
        </Field>
        {purchase ? (
          <Field id={`${ids}-claimable`} label={fm(ed.claimable)}>
            <Input
              id={`${ids}-claimable`}
              inputMode="decimal"
              value={claimable}
              disabled={editing}
              onChange={(e) => setClaimable(e.target.value)}
            />
          </Field>
        ) : null}
      </div>
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <section aria-labelledby={`${ids}-components`} className="flex flex-col gap-3">
          <h2 id={`${ids}-components`} className="text-lg font-semibold text-fg">
            {fm(ed.components)}
          </h2>
          {noTax ? null : (
            <>
              <ul className="flex flex-col gap-2">
                {rows.map((row, index) => {
                  const n = index + 1;
                  const chosen = available.find((c) => c.id === row.component);
                  return (
                    <li
                      key={index}
                      className="flex flex-wrap items-center gap-2"
                      data-component-row=""
                    >
                      <select
                        aria-label={fm(ed.component, { n })}
                        value={row.component}
                        onChange={(e) =>
                          setRows((all) =>
                            all.map((r, i) =>
                              i === index ? { ...r, component: e.target.value } : r,
                            ),
                          )
                        }
                        className="h-10 min-w-64 rounded-md border border-border bg-surface px-3 text-sm text-fg"
                      >
                        <option value="">{fm(ed.pickComponent)}</option>
                        {choices.map((c) => (
                          <option key={c.id} value={c.id}>
                            {fm(ed.componentOption, {
                              name: c.name,
                              rate: c.rate,
                              authority: c.authority,
                            })}
                          </option>
                        ))}
                      </select>
                      {purchase && chosen?.recoverable ? (
                        <Input
                          aria-label={fm(ed.recoverable, { n })}
                          inputMode="decimal"
                          value={row.recoverable}
                          placeholder={fm(ed.recoverablePlaceholder)}
                          className="w-24"
                          onChange={(e) =>
                            setRows((all) =>
                              all.map((r, i) =>
                                i === index ? { ...r, recoverable: e.target.value } : r,
                              ),
                            )
                          }
                        />
                      ) : null}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setRows((all) => all.filter((_, i) => i !== index))}
                      >
                        {fm(ed.remove, { n })}
                      </Button>
                    </li>
                  );
                })}
              </ul>
              <div>
                <Button
                  variant="secondary"
                  onClick={() => setRows((all) => [...all, { component: "", recoverable: "" }])}
                >
                  {fm(ed.add)}
                </Button>
              </div>
            </>
          )}
        </section>
        <section
          aria-labelledby={`${ids}-example`}
          className="flex flex-col gap-2 rounded-lg border border-border bg-surface-subtle p-4"
          data-live-example=""
        >
          <h2 id={`${ids}-example`} className="text-base font-semibold text-fg">
            {fm(ed.example)}
          </h2>
          <label htmlFor={`${ids}-amount`} className="text-xs text-fg-muted">
            {fm(ed.exampleAmount)}
          </label>
          <Input
            id={`${ids}-amount`}
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
          <Switch
            label={fm(ed.exampleInclusive)}
            checked={inclusive}
            onCheckedChange={setInclusive}
          />
          {example ? (
            <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm tabular-nums">
              <dt>{fm(ed.exampleNet)}</dt>
              <dd className="text-right">{money(example.out.net)}</dd>
              {example.out.components.map((c, i) => (
                <ExampleLine
                  key={`${c.key}-${i}`}
                  label={fm(ed.componentRate, {
                    name: example.parts[i]?.name ?? c.key,
                    rate: c.rate,
                  })}
                  value={money(c.amount)}
                />
              ))}
              {purchase ? (
                <>
                  <dt className="text-fg-muted">{fm(ed.exampleClaimable)}</dt>
                  <dd className="text-right" data-claimable="">
                    {money(example.out.claimable)}
                  </dd>
                  <dt className="text-fg-muted">{fm(ed.exampleCost)}</dt>
                  <dd className="text-right" data-cost="">
                    {money(example.out.cost)}
                  </dd>
                </>
              ) : null}
              <dt className="font-semibold">{fm(ed.exampleTotal)}</dt>
              <dd className="text-right font-semibold" data-total="">
                {money(example.out.gross)}
              </dd>
            </dl>
          ) : null}
        </section>
      </div>
      <div className="flex justify-end gap-3">
        <Link href={`/o/${org}/settings/tax-codes`} className="px-4 py-2 text-sm underline">
          {fm(ed.cancel)}
        </Link>
        <Button variant="primary" type="submit" disabled={saving}>
          {fm(editing ? ed.saveVersion : ed.save)}
        </Button>
      </div>
    </form>
  );
}

function ExampleLine({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd className="text-right">{value}</dd>
    </>
  );
}

function Field({
  id,
  label,
  hint,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-fg">
        {label}
      </label>
      {children}
      {hint ? (
        <p id={`${id}-hint`} className="text-xs text-fg-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
