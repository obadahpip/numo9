"use client";

import {
  Button,
  Checkbox,
  Dialog,
  ExplainPanel,
  Input,
  LoadingRegion,
  SkeletonText,
  StatusBadge,
  Switch,
  cn,
} from "@numo9/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useState, type ReactNode } from "react";

import { listConsoleProducts, type ProductDetail } from "@/catalogue/api";
import { useFormatMessage } from "@/i18n";

import {
  errorText,
  fieldErrors,
  ok,
  packagesApi,
  type ApiError,
  type PackageInput,
  type PlatformPackage,
} from "./api";
import { pm } from "./messages";
import { PriceTimeline } from "./PriceTimeline";
import { PricingCard } from "./PricingCard";
import { packageUrl } from "./PackagesScreen";

interface FormState {
  code: string;
  nameEn: string;
  nameFr: string;
  descriptionEn: string;
  descriptionFr: string;
  products: string[];
  maxUsers: string;
  unlimited: boolean;
  founding: boolean;
}

const EMPTY: FormState = {
  code: "",
  nameEn: "",
  nameFr: "",
  descriptionEn: "",
  descriptionFr: "",
  products: [],
  maxUsers: "",
  unlimited: true,
  founding: false,
};

function fromPackage(p: PlatformPackage): FormState {
  return {
    code: p.code,
    nameEn: p.name_i18n["en-CA"] ?? "",
    nameFr: p.name_i18n["fr-CA"] ?? "",
    descriptionEn: p.description_i18n["en-CA"] ?? "",
    descriptionFr: p.description_i18n["fr-CA"] ?? "",
    products: p.products.map((x) => x.code),
    maxUsers: p.limits.max_org_users === null ? "" : String(p.limits.max_org_users),
    unlimited: p.limits.max_org_users === null,
    founding: p.is_founding_eligible,
  };
}

function texts(en: string, fr: string): Record<string, string> {
  const result: Record<string, string> = { "en-CA": en.trim() };
  if (fr.trim()) result["fr-CA"] = fr.trim();
  return result;
}

type Load =
  | { kind: "loading" }
  | { kind: "ready"; pkg: PlatformPackage | null; products: ProductDetail[] }
  | { kind: "denied"; error: ApiError }
  | { kind: "notFound" }
  | { kind: "failed" };

/**
 * Platform console → package editor (U-02-T09), `/console/packages/new` and
 * `/console/packages/<code>`: code, names and descriptions (EN/FR), products as cards with a
 * switch (free sets are in every package; planned apps can't be added), user limit, founding
 * flag, and a live preview of the public pricing card from the unsaved form. Save draft /
 * Activate / Retire / Delete follow the package rules; the API's field errors show under each
 * field. Prices: the timeline below (U-02-T10).
 */
export function PackageEditor({ code }: { code: string | null }) {
  const fm = useFormatMessage();
  const router = useRouter();
  const ids = { form: useId() };
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [alert, setAlert] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<"retire" | "delete" | null>(null);

  useEffect(() => {
    let live = true;
    void Promise.all([
      code ? packagesApi.get(code) : Promise.resolve(null),
      listConsoleProducts(),
    ]).then(([pkg, products]) => {
      if (!live) return;
      const refused = [pkg, products].find((r) => r && (r.status === 401 || r.status === 403));
      if (refused) return setLoad({ kind: "denied", error: refused.body as ApiError });
      if (pkg && pkg.status === 404) return setLoad({ kind: "notFound" });
      if ((pkg && pkg.status !== 200) || products.status !== 200 || !("products" in products.body))
        return setLoad({ kind: "failed" });
      const current = pkg ? (pkg.body as PlatformPackage) : null;
      setLoad({
        kind: "ready",
        pkg: current,
        products: (products.body as { products: ProductDetail[] }).products,
      });
      setForm(current ? fromPackage(current) : EMPTY);
    });
    return () => {
      live = false;
    };
  }, [code]);

  const ready = load.kind === "ready" ? load : null;
  const sellable = useMemo(
    () => (ready?.products ?? []).filter((p) => p.kind !== "free_set" && p.status !== "retired"),
    [ready],
  );
  const free = useMemo(() => (ready?.products ?? []).filter((p) => p.kind === "free_set"), [ready]);

  if (load.kind === "loading") {
    return (
      <LoadingRegion label={fm(pm.loading)}>
        <SkeletonText lines={8} />
      </LoadingRegion>
    );
  }
  if (load.kind === "denied") {
    return (
      <ExplainPanel
        kind="permission"
        headingLevel={1}
        title={fm(pm.refusedTitle)}
        body={<p>{load.error.detail}</p>}
      />
    );
  }
  if (load.kind === "notFound") {
    return (
      <ExplainPanel
        kind="notFound"
        headingLevel={1}
        title={fm(pm.notFoundTitle)}
        body={
          <p>
            <Link href="/console/packages" className="underline">
              {fm(pm.notFoundBody)}
            </Link>
          </p>
        }
      />
    );
  }
  if (load.kind === "failed") {
    return (
      <p role="alert" className="text-fg-danger">
        {fm(pm.loadFailed)}
      </p>
    );
  }

  const pkg = load.pkg;
  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setStatus(null);
  };
  const toggle = (product: string, on: boolean) =>
    set("products", on ? [...form.products, product] : form.products.filter((p) => p !== product));

  const input = (): PackageInput | null => {
    const local: Record<string, string> = {};
    let maxUsers: number | null = null;
    if (!form.unlimited) {
      maxUsers = Number(form.maxUsers);
      if (!/^\d+$/.test(form.maxUsers.trim()) || maxUsers < 1)
        local.limits = fm(pm.maxUsersInvalid);
    }
    if (Object.keys(local).length) {
      setErrors(local);
      setAlert(fm(pm.fixErrors));
      return null;
    }
    const ordered = sellable.map((p) => p.code).filter((c) => form.products.includes(c));
    return {
      ...(pkg ? {} : { code: form.code.trim() }),
      name_i18n: texts(form.nameEn, form.nameFr),
      description_i18n: texts(form.descriptionEn, form.descriptionFr),
      products: ordered,
      limits: { max_org_users: maxUsers },
      is_founding_eligible: form.founding,
    };
  };

  const applied = (next: PlatformPackage, message: string) => {
    setLoad({ ...load, pkg: next });
    setForm(fromPackage(next));
    setErrors({});
    setAlert(null);
    setStatus(message);
  };

  const failed = (body: unknown) => {
    const byField = fieldErrors(body);
    setErrors(byField);
    setAlert(Object.keys(byField).length ? fm(pm.fixErrors) : (errorText(body) ?? fm(pm.failed)));
  };

  /** Save the form; returns the stored package (or null when refused). */
  const save = async (): Promise<PlatformPackage | null> => {
    const body = input();
    if (!body) return null;
    setBusy(true);
    const result = pkg ? await packagesApi.update(pkg.code, body) : await packagesApi.create(body);
    setBusy(false);
    if (!ok(result.status)) {
      failed(result.body);
      return null;
    }
    const saved = result.body as PlatformPackage;
    if (!pkg) {
      router.replace(packageUrl(saved.code));
    }
    applied(saved, fm(pm.saved, { name: saved.name }));
    return saved;
  };

  const activate = async () => {
    const saved = await save();
    if (!saved) return;
    setBusy(true);
    const result = await packagesApi.activate(saved.code);
    setBusy(false);
    if (ok(result.status)) {
      const next = result.body as PlatformPackage;
      applied(next, fm(pm.activated, { name: next.name }));
    } else failed(result.body);
  };

  const retire = async () => {
    if (!pkg) return;
    setConfirm(null);
    setBusy(true);
    const result = await packagesApi.retire(pkg.code);
    setBusy(false);
    if (ok(result.status)) {
      const next = result.body as PlatformPackage;
      applied(next, fm(pm.retired, { name: next.name }));
    } else failed(result.body);
  };

  const remove = async () => {
    if (!pkg) return;
    setConfirm(null);
    setBusy(true);
    const result = await packagesApi.remove(pkg.code);
    setBusy(false);
    if (result.status === 204) router.push("/console/packages");
    else failed(result.body);
  };

  const name = form.nameEn.trim() || pkg?.name || fm(pm.newTitle);
  const productNames = sellable.filter((p) => form.products.includes(p.code)).map((p) => p.name);
  const maxUsers = form.unlimited || !/^\d+$/.test(form.maxUsers) ? null : Number(form.maxUsers);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <Link href="/console/packages" className="text-sm font-semibold underline">
          {fm(pm.back)}
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold">{pkg ? pkg.name : fm(pm.newTitle)}</h1>
            {pkg ? <StatusBadge status={pkg.status} label={pkg.status_label} /> : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {pkg?.status === "draft" ? (
              <Button variant="danger" onClick={() => setConfirm("delete")} disabled={busy}>
                {fm(pm.delete)}
              </Button>
            ) : null}
            <Button variant="secondary" onClick={() => void save()} loading={busy}>
              {pkg ? fm(pm.save) : fm(pm.saveDraft)}
            </Button>
            {!pkg || pkg.status !== "active" ? (
              <Button onClick={() => void activate()} disabled={busy}>
                {fm(pm.activate)}
              </Button>
            ) : (
              <Button variant="secondary" onClick={() => setConfirm("retire")} disabled={busy}>
                {fm(pm.retire)}
              </Button>
            )}
          </div>
        </div>
      </div>
      {pkg?.status === "retired" ? (
        <p
          className="rounded-md border-2 border-border bg-surface-info-subtle px-4 py-3 text-sm"
          data-testid="retired-notice"
        >
          {fm(pm.retiredNotice, { count: pkg.subscriber_count })}
        </p>
      ) : null}
      {status ? (
        <p role="status" className="text-sm text-fg-muted">
          {status}
        </p>
      ) : null}
      {alert ? (
        <p
          role="alert"
          className="rounded-md border-2 border-border-danger bg-surface-danger-subtle px-4 py-3 text-sm"
        >
          {alert}
        </p>
      ) : null}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <form
          id={ids.form}
          aria-label={name}
          className="flex min-w-0 flex-col gap-6"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <Section title={fm(pm.details)}>
            <div className="grid gap-4 md:grid-cols-3">
              <TextInput
                label={fm(pm.code)}
                value={form.code}
                onChange={(v) => set("code", v.toLowerCase())}
                hint={fm(pm.codeHint)}
                error={errors.code}
                readOnly={pkg !== null}
                required
                mono
              />
              <TextInput
                label={fm(pm.nameEn)}
                value={form.nameEn}
                onChange={(v) => set("nameEn", v)}
                error={errors.name_i18n}
                maxLength={60}
                required
              />
              <TextInput
                label={fm(pm.nameFr)}
                value={form.nameFr}
                onChange={(v) => set("nameFr", v)}
                hint={fm(pm.frenchHint)}
                maxLength={60}
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <TextInput
                label={fm(pm.descriptionEn)}
                value={form.descriptionEn}
                onChange={(v) => set("descriptionEn", v)}
                error={errors.description_i18n}
                maxLength={300}
              />
              <TextInput
                label={fm(pm.descriptionFr)}
                value={form.descriptionFr}
                onChange={(v) => set("descriptionFr", v)}
                maxLength={300}
              />
            </div>
          </Section>
          <Section
            title={fm(pm.products)}
            intro={fm(pm.productsHint, { free: free.map((p) => p.name).join(", ") })}
          >
            {errors.products ? (
              <p className="text-sm text-fg-danger" data-testid="products-error">
                {errors.products}
              </p>
            ) : null}
            <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {sellable.map((product) => {
                const planned = product.status !== "active";
                const on = form.products.includes(product.code);
                return (
                  <li
                    key={product.code}
                    data-product-card={product.code}
                    data-selected={on}
                    className={cn(
                      "flex items-start justify-between gap-3 rounded-lg border-2 p-3",
                      on ? "border-border-strong bg-surface-accent-subtle" : "border-border",
                      planned && "border-dashed text-fg-muted",
                    )}
                  >
                    <div className="flex flex-col gap-1">
                      <span className="font-semibold">{product.name}</span>
                      <span className="text-xs text-fg-muted">
                        {planned
                          ? fm(pm.plannedProduct)
                          : fm(pm.featureCount, { count: product.feature_count })}
                      </span>
                    </div>
                    <Switch
                      aria-label={fm(pm.include, { product: product.name })}
                      checked={on}
                      disabled={planned && !on}
                      onCheckedChange={(next) => toggle(product.code, next)}
                    />
                  </li>
                );
              })}
            </ul>
          </Section>
          <Section title={fm(pm.limits)}>
            <div className="flex flex-wrap items-end gap-4">
              <TextInput
                label={fm(pm.maxUsers)}
                value={form.unlimited ? "" : form.maxUsers}
                onChange={(v) => {
                  set("maxUsers", v);
                  if (v.trim()) set("unlimited", false);
                }}
                hint={fm(pm.maxUsersHint)}
                error={errors.limits}
                inputMode="numeric"
                className="w-56"
              />
              <div className="pb-7">
                <Checkbox
                  label={fm(pm.unlimited)}
                  checked={form.unlimited}
                  onCheckedChange={(next) => set("unlimited", next === true)}
                />
              </div>
            </div>
          </Section>
          <Section title={fm(pm.founding)}>
            <Switch
              label={fm(pm.founding)}
              description={fm(pm.foundingHint)}
              checked={form.founding}
              onCheckedChange={(next) => set("founding", next)}
            />
          </Section>
        </form>
        <aside className="flex flex-col gap-2 lg:sticky lg:top-4 lg:self-start">
          <h2 className="text-xs font-bold uppercase tracking-wide text-fg-muted">
            {fm(pm.preview)}
          </h2>
          <PricingCard
            label={fm(pm.preview)}
            name={form.nameEn}
            description={form.descriptionEn}
            products={productNames}
            freeProducts={free.map((p) => p.name)}
            maxUsers={maxUsers}
            founding={form.founding}
            prices={{
              month: pkg?.current_prices.month?.amount_cents ?? null,
              year: pkg?.current_prices.year?.amount_cents ?? null,
            }}
          />
        </aside>
      </div>
      {pkg ? (
        <PriceTimeline pkg={pkg} onChanged={(next) => setLoad({ ...load, pkg: next })} />
      ) : null}
      <Dialog
        open={confirm !== null}
        onOpenChange={(open) => (open ? undefined : setConfirm(null))}
        title={
          confirm === "delete"
            ? fm(pm.deleteTitle, { name: pkg?.name ?? "" })
            : fm(pm.retireTitle, { name: pkg?.name ?? "" })
        }
        description={
          confirm === "delete"
            ? fm(pm.deleteBody)
            : fm(pm.retireBody, { count: pkg?.subscriber_count ?? 0 })
        }
        closeLabel={fm(pm.close)}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirm(null)}>
              {fm(pm.cancel)}
            </Button>
            {confirm === "delete" ? (
              <Button variant="danger" onClick={() => void remove()}>
                {fm(pm.delete)}
              </Button>
            ) : (
              <Button onClick={() => void retire()}>{fm(pm.retire)}</Button>
            )}
          </div>
        }
      />
    </div>
  );
}

function Section({
  title,
  intro,
  children,
}: {
  title: string;
  intro?: string;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-col gap-1">
        <h2 id={id} className="text-lg font-semibold">
          {title}
        </h2>
        {intro ? <p className="text-sm text-fg-muted">{intro}</p> : null}
      </div>
      {children}
    </section>
  );
}

function TextInput({
  label,
  value,
  onChange,
  hint,
  error,
  readOnly,
  required,
  mono,
  maxLength,
  inputMode,
  className,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  error?: string;
  readOnly?: boolean;
  required?: boolean;
  mono?: boolean;
  maxLength?: number;
  inputMode?: "numeric";
  className?: string;
}) {
  const id = useId();
  const describedBy = [hint ? `${id}-hint` : null, error ? `${id}-error` : null]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-semibold">
        {label}
      </label>
      <Input
        id={id}
        value={value}
        readOnly={readOnly}
        required={required}
        maxLength={maxLength}
        inputMode={inputMode}
        invalid={Boolean(error)}
        aria-describedby={describedBy || undefined}
        className={mono ? "font-mono" : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      {hint ? (
        <p id={`${id}-hint`} className="text-xs text-fg-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
