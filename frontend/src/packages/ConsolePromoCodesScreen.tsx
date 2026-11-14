"use client";

import {
  Button,
  Checkbox,
  Dialog,
  EmptyState,
  ExplainPanel,
  Input,
  LoadingRegion,
  RadioGroup,
  Select,
  SkeletonTable,
  StatusBadge,
  formatDate,
  type AppLocale,
  type StatusKey,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState, type ReactNode } from "react";

import { useFormatMessage } from "@/i18n";

import {
  errorText,
  fieldErrors,
  ok,
  packagesApi,
  promosApi,
  type ApiError,
  type NamedCode,
  type PromoCode,
  type PromoDuration,
  type PromoInput,
  type PromoKind,
  type PromoStatus,
} from "./api";
import { om, pm } from "./messages";
import { money, parseCents } from "./money";

/** Promo statuses on the shared status vocabulary (tone only; the label is the API's). */
const STATUS_KEY: Record<PromoStatus, StatusKey> = {
  active: "active",
  used_up: "archived",
  expired: "cancelled",
};

/**
 * Platform console → Promo codes (U-02-T11), `/console/promo-codes`: every code with its
 * discount, duration, packages, a usage bar (redemptions ÷ maximum), expiry and status; create a
 * code in a dialog; expire an active code now (redemptions already made are kept). Platform
 * owner only (the API's 403 shows the refusal panel).
 */
export function ConsolePromoCodesScreen() {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const [codes, setCodes] = useState<PromoCode[] | null>(null);
  const [packages, setPackages] = useState<NamedCode[]>([]);
  const [refusal, setRefusal] = useState<ApiError | null>(null);
  const [failed, setFailed] = useState(false);
  const [creating, setCreating] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [alert, setAlert] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [list, pkgs] = await Promise.all([promosApi.list(), packagesApi.list()]);
    if (list.status === 401 || list.status === 403) return setRefusal(list.body as ApiError);
    if (list.status !== 200) return setFailed(true);
    setCodes((list.body as { promo_codes: PromoCode[] }).promo_codes);
    if (pkgs.status === 200) {
      const all = (pkgs.body as { packages: (NamedCode & { status: string })[] }).packages;
      setPackages(
        all.filter((p) => p.status !== "retired").map(({ code, name }) => ({ code, name })),
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (refusal) {
    return (
      <ExplainPanel
        kind="permission"
        headingLevel={1}
        title={fm(pm.refusedTitle)}
        body={<p>{refusal.detail}</p>}
      />
    );
  }

  const expire = async (code: PromoCode) => {
    setAlert(null);
    const result = await promosApi.expire(code.code);
    if (!ok(result.status)) {
      setAlert(errorText(result.body) ?? fm(pm.failed));
      return;
    }
    const next = result.body as PromoCode;
    setCodes((prev) => (prev ?? []).map((c) => (c.code === next.code ? next : c)));
    setStatus(fm(om.expired, { code: next.code }));
  };

  const discount = (code: PromoCode) =>
    code.kind === "percent"
      ? fm(om.percentOff, { percent: code.percent_off ?? 0 })
      : fm(om.amountOff, { amount: money(code.amount_off_cents ?? 0, locale) });
  const duration = (code: PromoCode) =>
    code.duration === "repeating"
      ? fm(om.months, { count: code.duration_months ?? 0 })
      : code.duration_label;

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-semibold">{fm(om.title)}</h1>
          <p className="text-fg-muted">{fm(om.intro)}</p>
        </div>
        <Button onClick={() => setCreating(true)}>{fm(om.newCode)}</Button>
      </header>
      {status ? (
        <p role="status" className="text-sm text-fg-muted">
          {status}
        </p>
      ) : null}
      {alert || failed ? (
        <p role="alert" className="text-fg-danger">
          {alert ?? fm(om.loadFailed)}
        </p>
      ) : null}
      {codes === null && !failed ? (
        <LoadingRegion label={fm(om.loading)}>
          <SkeletonTable rows={4} columns={7} />
        </LoadingRegion>
      ) : null}
      {codes && codes.length === 0 ? (
        <EmptyState
          title={fm(om.emptyTitle)}
          body={fm(om.emptyBody)}
          actions={[
            <Button key="new" onClick={() => setCreating(true)}>
              {fm(om.newCode)}
            </Button>,
          ]}
        />
      ) : null}
      {codes && codes.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-start text-sm">
            <caption className="sr-only">{fm(om.title)}</caption>
            <thead className="bg-surface-muted text-fg-muted">
              <tr>
                {[
                  om.colCode,
                  om.colDiscount,
                  om.colDuration,
                  om.colPackages,
                  om.colUsed,
                  om.colExpires,
                  om.colStatus,
                  om.colActions,
                ].map((column) => (
                  <th key={column.id} scope="col" className="px-4 py-2 text-start font-medium">
                    {fm(column)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {codes.map((code) => (
                <tr key={code.code} data-code={code.code} className="border-t border-border">
                  <td className="px-4 py-2">
                    <span className="font-mono font-semibold">{code.code}</span>
                    {code.description ? (
                      <div className="text-xs text-fg-muted">{code.description}</div>
                    ) : null}
                  </td>
                  <td className="px-4 py-2">{discount(code)}</td>
                  <td className="px-4 py-2">{duration(code)}</td>
                  <td className="px-4 py-2">
                    {code.packages.length
                      ? code.packages.map((p) => p.name).join(", ")
                      : fm(om.anyPackage)}
                  </td>
                  <td className="px-4 py-2">
                    <UsageBar code={code} />
                  </td>
                  <td className="px-4 py-2">
                    {code.expires_at
                      ? formatDate(new Date(code.expires_at), { locale })
                      : fm(om.never)}
                  </td>
                  <td className="px-4 py-2">
                    <StatusBadge status={STATUS_KEY[code.status]} label={code.status_label} />
                  </td>
                  <td className="px-4 py-2">
                    {code.status === "active" ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        aria-label={fm(om.expireLabel, { code: code.code })}
                        onClick={() => void expire(code)}
                      >
                        {fm(om.expire)}
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <CreateDialog
        open={creating}
        packages={packages}
        onClose={() => setCreating(false)}
        onCreated={(code) => {
          setCreating(false);
          setCodes((prev) => [code, ...(prev ?? [])]);
          setStatus(fm(om.created, { code: code.code }));
        }}
      />
    </div>
  );
}

function UsageBar({ code }: { code: PromoCode }) {
  const fm = useFormatMessage();
  const max = code.max_redemptions;
  const share = max ? Math.min(code.redemptions_count / max, 1) : 0;
  return (
    <div className="flex min-w-32 flex-col gap-1">
      <div
        role="progressbar"
        aria-label={fm(om.usageLabel, { code: code.code })}
        aria-valuenow={code.redemptions_count}
        aria-valuemin={0}
        aria-valuemax={max ?? undefined}
        className="h-2 overflow-hidden rounded bg-surface-muted"
      >
        <div
          className="h-full bg-surface-accent"
          data-testid="usage-fill"
          style={{ width: `${(share * 100).toFixed(1)}%` }}
        />
      </div>
      <span className="text-xs text-fg-muted">
        {max
          ? fm(om.usage, { used: code.redemptions_count, max })
          : fm(om.usageNoLimit, { used: code.redemptions_count })}
      </span>
    </div>
  );
}

const BLANK = {
  code: "",
  description: "",
  kind: "percent" as PromoKind,
  percent: "",
  amount: "",
  duration: "once" as PromoDuration,
  months: "",
  maxUses: "",
  expiresOn: "",
  packages: [] as string[],
};

function CreateDialog({
  open,
  packages,
  onClose,
  onCreated,
}: {
  open: boolean;
  packages: NamedCode[];
  onClose: () => void;
  onCreated: (code: PromoCode) => void;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = { kind: useId(), duration: useId(), packages: useId() };
  const [form, setForm] = useState(BLANK);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [alert, setAlert] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) {
      setForm(BLANK);
      setErrors({});
      setAlert(null);
    }
  }, [open]);

  const set = <K extends keyof typeof BLANK>(key: K, value: (typeof BLANK)[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));
  const whole = (text: string): number | null | "bad" =>
    !text.trim() ? null : /^\d+$/.test(text.trim()) ? Number(text) : "bad";

  const submit = async () => {
    const local: Record<string, string> = {};
    const percent = whole(form.percent);
    const months = whole(form.months);
    const maxUses = whole(form.maxUses);
    const cents = form.kind === "fixed" ? parseCents(form.amount, locale) : null;
    if (form.kind === "percent" && (percent === null || percent === "bad"))
      local.percent_off = fm(om.number);
    if (form.kind === "fixed" && !cents) local.amount_off_cents = fm(om.amountInvalid);
    if (form.duration === "repeating" && (months === null || months === "bad"))
      local.duration_months = fm(om.number);
    if (maxUses === "bad") local.max_redemptions = fm(om.number);
    setErrors(local);
    if (Object.keys(local).length) return;
    const input: PromoInput = {
      code: form.code.trim(),
      description: form.description.trim(),
      kind: form.kind,
      percent_off: form.kind === "percent" ? (percent as number) : null,
      amount_off_cents: form.kind === "fixed" ? cents : null,
      duration: form.duration,
      duration_months: form.duration === "repeating" ? (months as number) : null,
      max_redemptions: maxUses === "bad" ? null : maxUses,
      expires_at: form.expiresOn ? `${form.expiresOn}T23:59:59` : null,
      packages: form.packages,
    };
    setBusy(true);
    const result = await promosApi.create(input);
    setBusy(false);
    if (ok(result.status)) onCreated(result.body as PromoCode);
    else {
      const byField = fieldErrors(result.body);
      setErrors(byField);
      setAlert(Object.keys(byField).length ? null : (errorText(result.body) ?? fm(pm.failed)));
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => (next ? undefined : onClose())}
      title={fm(om.newCode)}
      closeLabel={fm(pm.close)}
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {fm(pm.cancel)}
          </Button>
          <Button onClick={() => void submit()} loading={busy}>
            {fm(om.create)}
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={fm(om.code)} hint={fm(om.codeHint)} error={errors.code}>
            {(props) => (
              <Input
                {...props}
                className="font-mono uppercase"
                value={form.code}
                maxLength={40}
                onChange={(e) => set("code", e.target.value)}
              />
            )}
          </Field>
          <Field label={fm(om.description)} error={errors.description}>
            {(props) => (
              <Input
                {...props}
                value={form.description}
                maxLength={200}
                onChange={(e) => set("description", e.target.value)}
              />
            )}
          </Field>
        </div>
        <div className="flex flex-col gap-1.5">
          <span id={ids.kind} className="text-sm font-semibold">
            {fm(om.kind)}
          </span>
          <RadioGroup
            aria-labelledby={ids.kind}
            value={form.kind}
            onValueChange={(v) => set("kind", v as PromoKind)}
            options={[
              { value: "percent", label: fm(om.kindPercent) },
              { value: "fixed", label: fm(om.kindFixed) },
            ]}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          {form.kind === "percent" ? (
            <Field label={fm(om.percent)} error={errors.percent_off}>
              {(props) => (
                <Input
                  {...props}
                  inputMode="numeric"
                  numeric
                  suffix="%"
                  value={form.percent}
                  onChange={(e) => set("percent", e.target.value)}
                />
              )}
            </Field>
          ) : (
            <Field label={fm(om.amount)} error={errors.amount_off_cents}>
              {(props) => (
                <Input
                  {...props}
                  inputMode="decimal"
                  numeric
                  prefix="$"
                  value={form.amount}
                  onChange={(e) => set("amount", e.target.value)}
                />
              )}
            </Field>
          )}
          <div className="flex flex-col gap-1.5">
            <span id={ids.duration} className="text-sm font-semibold">
              {fm(om.duration)}
            </span>
            <Select
              aria-labelledby={ids.duration}
              value={form.duration}
              onValueChange={(v) => set("duration", v as PromoDuration)}
              options={[
                { value: "once", label: fm(om.durationOnce) },
                { value: "repeating", label: fm(om.durationRepeating) },
                { value: "forever", label: fm(om.durationForever) },
              ]}
            />
          </div>
          {form.duration === "repeating" ? (
            <Field label={fm(om.monthsField)} error={errors.duration_months}>
              {(props) => (
                <Input
                  {...props}
                  inputMode="numeric"
                  numeric
                  value={form.months}
                  onChange={(e) => set("months", e.target.value)}
                />
              )}
            </Field>
          ) : null}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={fm(om.maxUses)} error={errors.max_redemptions}>
            {(props) => (
              <Input
                {...props}
                inputMode="numeric"
                numeric
                value={form.maxUses}
                onChange={(e) => set("maxUses", e.target.value)}
              />
            )}
          </Field>
          <Field label={fm(om.expiresOn)} hint={fm(om.expiresHint)} error={errors.expires_at}>
            {(props) => (
              <Input
                {...props}
                type="date"
                value={form.expiresOn}
                onChange={(e) => set("expiresOn", e.target.value)}
              />
            )}
          </Field>
        </div>
        {packages.length ? (
          <fieldset className="flex flex-col gap-2" aria-describedby={`${ids.packages}-hint`}>
            <legend className="text-sm font-semibold">{fm(om.packages)}</legend>
            <p id={`${ids.packages}-hint`} className="text-xs text-fg-muted">
              {fm(om.packagesHint)}
            </p>
            <div className="flex flex-wrap gap-4">
              {packages.map((p) => (
                <Checkbox
                  key={p.code}
                  label={p.name}
                  checked={form.packages.includes(p.code)}
                  onCheckedChange={(next) =>
                    set(
                      "packages",
                      next === true
                        ? [...form.packages, p.code]
                        : form.packages.filter((c) => c !== p.code),
                    )
                  }
                />
              ))}
            </div>
            {errors.packages ? <p className="text-sm text-fg-danger">{errors.packages}</p> : null}
          </fieldset>
        ) : null}
        {alert ? (
          <p role="alert" className="text-sm text-fg-danger">
            {alert}
          </p>
        ) : null}
      </div>
    </Dialog>
  );
}

function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: (props: {
    id: string;
    invalid: boolean;
    "aria-describedby": string | undefined;
  }) => ReactNode;
}) {
  const id = useId();
  const describedBy =
    [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") ||
    undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-semibold">
        {label}
      </label>
      {children({ id, invalid: Boolean(error), "aria-describedby": describedBy })}
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
