"use client";

/**
 * Console → organisation → Product grants (U-03-T14): give the organisation a product for N days
 * with a reason (platform owners), see every grant (active, ended, removed) and remove an active
 * one. Grants and removals are recorded in the organisation's audit log; `onChanged` lets the page
 * reload its recent audit events so the entry shows at once.
 */
import { Badge, Button, ErrorState, formatDate, Input } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useEffect, useId, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { g } from "./grantMessages";
import { grantProduct, listGrants, removeGrant, type GrantList, type ProductGrant } from "./grants";

export function ProductGrants({
  organisationId,
  canGrant,
  timeZone,
  onChanged,
}: {
  organisationId: string;
  canGrant: boolean;
  timeZone: string;
  onChanged?: () => void;
}) {
  const fm = useFormatMessage();
  const locale = useLocale() as "en-CA" | "fr-CA";
  const ids = {
    product: useId(),
    days: useId(),
    reason: useId(),
    daysHint: useId(),
    reasonHint: useId(),
  };
  const [data, setData] = useState<GrantList | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [product, setProduct] = useState("");
  const [days, setDays] = useState("14");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<{
    field: "product" | "days" | "reason" | "form";
    text: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    let cancelled = false;
    void listGrants(organisationId).then((result) => {
      if (cancelled) return;
      if (result.status === 200 && Array.isArray(result.body.overrides)) {
        setData(result.body);
        setFailed(false);
      } else setFailed(true);
    });
    return () => {
      cancelled = true;
    };
  }, [organisationId, attempt]);

  const day = (iso: string) => formatDate(new Date(iso), { locale, timeZone });
  const max = data?.max_days ?? 365;

  const submit = async () => {
    const count = Number(days);
    if (!product) return setError({ field: "product", text: fm(g.invalidProduct) });
    if (!Number.isInteger(count) || count < 1 || count > max)
      return setError({ field: "days", text: fm(g.invalidDays, { max }) });
    if (reason.trim().length < 5) return setError({ field: "reason", text: fm(g.invalidReason) });
    setBusy(true);
    const result = await grantProduct(organisationId, {
      product,
      days: count,
      reason: reason.trim(),
    });
    setBusy(false);
    if (result.status === 201 && "id" in result.body) {
      const grant = result.body as ProductGrant;
      setStatus(fm(g.granted, { product: grant.product_name, date: day(grant.expires_at) }));
      setReason("");
      setProduct("");
      setError(null);
      setAttempt((n) => n + 1);
      onChanged?.();
      return;
    }
    setError({ field: "form", text: result.status === 403 ? fm(g.forbidden) : fm(g.failed) });
  };

  const remove = async (grant: ProductGrant) => {
    const result = await removeGrant(organisationId, grant.id);
    if (result.status === 204) {
      setStatus(fm(g.removed, { product: grant.product_name }));
      setAttempt((n) => n + 1);
      onChanged?.();
    } else
      setError({ field: "form", text: result.status === 403 ? fm(g.forbidden) : fm(g.failed) });
  };

  const stateBadge = (grant: ProductGrant) =>
    grant.state === "active" ? (
      <Badge tone="success">{fm(g.stateActive)}</Badge>
    ) : grant.state === "expired" ? (
      <Badge tone="neutral">{fm(g.stateExpired)}</Badge>
    ) : (
      <Badge tone="neutral">{fm(g.stateRemoved)}</Badge>
    );

  return (
    <section
      aria-labelledby="console-grants"
      className="flex flex-col gap-3 rounded-lg border border-border p-4"
      data-product-grants=""
    >
      <h2 id="console-grants" className="text-lg font-bold text-fg">
        {fm(g.title)}
      </h2>
      <p className="text-sm text-fg-muted">{fm(g.intro)}</p>
      <p role="status" className="sr-only">
        {status}
      </p>
      {failed ? (
        <ErrorState
          title={fm(g.loadFailed)}
          retryLabel={fm(g.retry)}
          onRetry={() => setAttempt((n) => n + 1)}
          headingLevel={3}
        />
      ) : data ? (
        <>
          {canGrant ? (
            <form
              className="grid gap-3 sm:grid-cols-[1fr_8rem]"
              onSubmit={(event) => {
                event.preventDefault();
                void submit();
              }}
              noValidate
            >
              <div className="flex flex-col gap-1">
                <label htmlFor={ids.product} className="text-sm font-semibold text-fg">
                  {fm(g.product)}
                </label>
                <select
                  id={ids.product}
                  className="min-h-touch-target rounded-md border border-border-strong bg-surface px-2 text-sm"
                  value={product}
                  aria-invalid={error?.field === "product" || undefined}
                  onChange={(event) => {
                    setProduct(event.target.value);
                    setError(null);
                  }}
                >
                  <option value="">{fm(g.chooseProduct)}</option>
                  {data.products.map((p) => (
                    <option key={p.code} value={p.code}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor={ids.days} className="text-sm font-semibold text-fg">
                  {fm(g.days)}
                </label>
                <Input
                  id={ids.days}
                  inputMode="numeric"
                  value={days}
                  invalid={error?.field === "days"}
                  aria-describedby={ids.daysHint}
                  onChange={(event) => {
                    setDays(event.target.value);
                    setError(null);
                  }}
                />
              </div>
              <p id={ids.daysHint} className="text-xs text-fg-muted sm:col-span-2">
                {fm(g.daysHint, { max })}
              </p>
              <div className="flex flex-col gap-1 sm:col-span-2">
                <label htmlFor={ids.reason} className="text-sm font-semibold text-fg">
                  {fm(g.reason)}
                </label>
                <Input
                  id={ids.reason}
                  value={reason}
                  maxLength={300}
                  invalid={error?.field === "reason"}
                  aria-describedby={ids.reasonHint}
                  onChange={(event) => {
                    setReason(event.target.value);
                    setError(null);
                  }}
                />
                <p id={ids.reasonHint} className="text-xs text-fg-muted">
                  {fm(g.reasonHint)}
                </p>
              </div>
              {error ? (
                <p role="alert" className="text-sm text-fg-danger sm:col-span-2">
                  {error.text}
                </p>
              ) : null}
              <div className="sm:col-span-2">
                <Button type="submit" variant="primary" loading={busy}>
                  {fm(g.grant)}
                </Button>
              </div>
            </form>
          ) : null}
          {data.overrides.length === 0 ? (
            <p className="text-sm text-fg-muted">{fm(g.none)}</p>
          ) : (
            <ul className="flex flex-col gap-2 text-sm" data-grants="">
              {data.overrides.map((grant) => (
                <li
                  key={grant.id}
                  className="flex flex-wrap items-center gap-2"
                  data-grant={grant.id}
                >
                  {stateBadge(grant)}
                  <span>
                    {fm(g.line, {
                      product: grant.product_name,
                      date: day(grant.expires_at),
                      reason: grant.reason,
                      by: grant.granted_by,
                    })}
                  </span>
                  {canGrant && grant.state === "active" ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={fm(g.removeLabel, { product: grant.product_name })}
                      onClick={() => void remove(grant)}
                    >
                      {fm(g.remove)}
                    </Button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : null}
    </section>
  );
}
