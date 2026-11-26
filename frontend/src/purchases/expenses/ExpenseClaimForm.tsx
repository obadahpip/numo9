"use client";

/**
 * Expense claim form (E-04-T09), `/o/:org/purchases/expense-claims/new` and `…/:id/edit`: an
 * employee's claim on a phone or a desktop — one card per receipt or trip, stacked on a narrow
 * screen (390 px) and laid out in columns from `sm`.
 *
 * - **Receipt**: date, merchant, amount (tax included, the server splits the tax), the
 *   **category chips** — the categories the person uses most first (`/categories`), the rest in
 *   "More categories" — the tax code (the province's standard code by default), and the receipt
 *   itself: **"Take a photo or choose a file"** opens the camera on a phone
 *   (`capture="environment"`, images and PDF), uploaded with the A-06 presigned flow
 *   (`/expense-claims/receipts`); a photo already uploaded before is flagged.
 * - **Trip**: date, from, to and kilometres; the amount at the CRA rate is shown live (E-04-T10).
 * - **Save draft** creates or updates the claim; **Submit for approval** saves then submits and
 *   opens the claim. The server's refusal (a missing category, a receipt required above the
 *   threshold) is shown as it says it.
 */
import { Button, Input, formatMoney, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

import { precheck, sendToBucket } from "@/files/upload";
import { useFormatMessage } from "@/i18n";

import {
  expenseClaimsApi,
  type Category,
  type CategoryList,
  type ClaimInput,
  type ExpenseClaim,
} from "./api";
import { Labelled, type FormLine } from "./fields";
import { MileageLine } from "./MileageLine";
import { fm as fmm } from "./formMessages";

/** How many category chips show before "More categories". */
export const CHIP_COUNT = 6;

let counter = 0;
const nextKey = () => `line-${++counter}`;

export function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function blankLine(kind: FormLine["kind"], taxCode: string | null = null): FormLine {
  return {
    key: nextKey(),
    kind,
    date: today(),
    merchant: "",
    description: "",
    amount: "",
    account: null,
    taxCode: kind === "receipt" ? taxCode : null,
    receipt: null,
    upload: "idle",
    fromPlace: "",
    toPlace: "",
    km: "",
  };
}

export function fromClaim(claim: ExpenseClaim): FormLine[] {
  return claim.lines.map((line) => ({
    ...blankLine(line.kind),
    date: line.date,
    merchant: line.merchant ?? "",
    description: line.description,
    amount: line.kind === "receipt" ? line.amount : "",
    account: line.account?.id ?? null,
    taxCode: line.tax_code?.id ?? null,
    receipt: line.receipt ?? null,
    fromPlace: line.from_place ?? "",
    toPlace: line.to_place ?? "",
    km: line.distance_km ?? "",
  }));
}

export function toInput(title: string, notes: string, lines: FormLine[]): ClaimInput {
  return {
    title: title.trim(),
    notes,
    lines: lines.map((line) =>
      line.kind === "mileage"
        ? {
            kind: "mileage",
            date: line.date,
            description: line.description,
            account: line.account,
            from_place: line.fromPlace,
            to_place: line.toPlace,
            distance_km: line.km,
          }
        : {
            kind: "receipt",
            date: line.date,
            description: line.description,
            merchant: line.merchant,
            account: line.account,
            amount: line.amount || "0",
            tax_code: line.taxCode,
            receipt: line.receipt?.id ?? null,
          },
    ),
  };
}

const SELECT =
  "min-h-touch-target w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-fg";

export interface ExpenseClaimFormProps {
  org: string;
  /** Edit this claim (a draft or a rejected claim); a new claim otherwise. */
  id?: string;
  /** Open a page (tests pass a spy); default: the browser goes there. */
  navigate?: (href: string) => void;
}

export function ExpenseClaimForm({ org, id, navigate }: ExpenseClaimFormProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [claimId, setClaimId] = useState<string | undefined>(id);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<FormLine[]>([]);
  const [lists, setLists] = useState<CategoryList | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(!id);

  useEffect(() => {
    let live = true;
    void expenseClaimsApi
      .categories(org)
      .catch(() => null)
      .then((result) => {
        if (!live || result?.status !== 200) return;
        setLists(result.body);
        if (!id)
          setLines((now) =>
            now.length ? now : [blankLine("receipt", result.body.default_tax_code)],
          );
      });
    if (id) {
      void expenseClaimsApi
        .get(org, id)
        .catch(() => null)
        .then((result) => {
          if (!live) return;
          if (result?.status === 200) {
            setTitle(result.body.title);
            setNotes(result.body.notes);
            setLines(fromClaim(result.body));
            setLoaded(true);
          } else setError(result?.body?.detail ?? fm(fmm.failed));
        });
    }
    return () => {
      live = false;
    };
  }, [org, id, fm]);

  const change = useCallback((key: string, patch: Partial<FormLine>) => {
    setLines((now) => now.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  }, []);
  const remove = (key: string) => setLines((now) => now.filter((line) => line.key !== key));
  const add = (kind: FormLine["kind"]) =>
    setLines((now) => [...now, blankLine(kind, lists?.default_tax_code ?? null)]);

  const total = useMemo(
    () =>
      lines
        .filter((line) => line.kind === "receipt")
        .reduce((sum, line) => sum + (Number(line.amount) || 0), 0),
    [lines],
  );

  const save = async (): Promise<ExpenseClaim | null> => {
    setError(null);
    if (!title.trim()) {
      setError(fm(fmm.titleRequired));
      return null;
    }
    const body = toInput(title, notes, lines);
    const result = await (
      claimId ? expenseClaimsApi.update(org, claimId, body) : expenseClaimsApi.create(org, body)
    ).catch(() => null);
    if (result && (result.status === 200 || result.status === 201)) {
      setClaimId(result.body.id);
      return result.body;
    }
    setError(result?.body?.detail ?? fm(fmm.checkLines));
    return null;
  };

  const go = (href: string) => (navigate ? navigate(href) : window.location.assign(href));

  const act = async (submit: boolean) => {
    setBusy(true);
    setStatus(null);
    const saved = await save();
    if (saved && submit) {
      const sent = await expenseClaimsApi.submit(org, saved.id).catch(() => null);
      setBusy(false);
      if (sent?.status === 200) {
        setStatus(fm(fmm.submitted, { number: sent.body.number }));
        go(`/o/${org}/purchases/expense-claims/${sent.body.id}`);
        return;
      }
      setError(sent?.body?.detail ?? fm(fmm.failed));
      return;
    }
    setBusy(false);
    if (saved) setStatus(fm(fmm.saved));
  };

  if (!loaded) {
    return (
      <p role={error ? "alert" : "status"} className="p-4 text-sm text-fg-muted">
        {error ?? fm(fmm.loading)}
      </p>
    );
  }

  return (
    <form
      className="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4"
      aria-labelledby={`${ids}-title`}
      onSubmit={(event) => {
        event.preventDefault();
        void act(true);
      }}
    >
      <h1 id={`${ids}-title`} className="text-xl font-semibold text-fg">
        {claimId ? fm(fmm.editHeading) : fm(fmm.newHeading)}
      </h1>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${ids}-name`} className="text-sm font-medium text-fg">
          {fm(fmm.titleLabel)}
        </label>
        <Input
          id={`${ids}-name`}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={fm(fmm.titlePlaceholder)}
          maxLength={200}
        />
      </div>
      <ol className="flex flex-col gap-3" aria-label={fm(fmm.linesLabel)}>
        {lines.map((line, index) => (
          <li
            key={line.key}
            className="rounded-lg border border-border bg-surface p-3"
            data-line-kind={line.kind}
          >
            {line.kind === "receipt" ? (
              <ReceiptCard
                org={org}
                line={line}
                index={index}
                lists={lists}
                onChange={(patch) => change(line.key, patch)}
                onRemove={() => remove(line.key)}
              />
            ) : (
              <MileageLine
                org={org}
                claimId={claimId}
                line={line}
                index={index}
                lines={lines}
                onChange={(patch) => change(line.key, patch)}
                onRemove={() => remove(line.key)}
              />
            )}
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="secondary" onClick={() => add("receipt")}>
          {fm(fmm.addReceipt)}
        </Button>
        <Button type="button" variant="secondary" onClick={() => add("mileage")}>
          {fm(fmm.addTrip)}
        </Button>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${ids}-notes`} className="text-sm font-medium text-fg">
          {fm(fmm.notes)}
        </label>
        <textarea
          id={`${ids}-notes`}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="w-full rounded-md border border-border-strong bg-surface p-2 text-sm text-fg"
        />
      </div>
      <p className="text-sm text-fg-muted" data-receipts-total="">
        {fm(fmm.receiptsTotal, { amount: formatMoney(total.toFixed(2), { locale }) })}
      </p>
      {status ? (
        <p role="status" className="text-sm text-fg">
          {status}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-fg-danger">
          {error}
        </p>
      ) : null}
      <div className="sticky bottom-0 flex flex-col gap-2 border-t border-border bg-surface py-3 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" disabled={busy} onClick={() => void act(false)}>
          {fm(fmm.saveDraft)}
        </Button>
        <Button type="submit" disabled={busy}>
          {fm(fmm.submit)}
        </Button>
      </div>
    </form>
  );
}

interface CardProps {
  org: string;
  line: FormLine;
  index: number;
  onChange: (patch: Partial<FormLine>) => void;
  onRemove: () => void;
}

function ReceiptCard({
  org,
  line,
  index,
  lists,
  onChange,
  onRemove,
}: CardProps & { lists: CategoryList | null }) {
  const fm = useFormatMessage();
  const ids = useId();
  const file = useRef<HTMLInputElement>(null);
  const categories = lists?.categories ?? [];
  const chips = categories.slice(0, CHIP_COUNT);
  const chosenInMore = line.account && !chips.some((c) => c.id === line.account);

  const upload = async (picked: File) => {
    if (precheck(picked)) {
      onChange({ upload: "refused" });
      return;
    }
    onChange({ upload: "uploading" });
    const started = await expenseClaimsApi
      .startReceipt(org, picked.name, picked.size)
      .catch(() => null);
    if (started?.status !== 201 || !started.body.upload) {
      onChange({ upload: "failed" });
      return;
    }
    const sent = await sendToBucket(started.body.upload, picked, () => undefined);
    if (sent < 200 || sent >= 300) {
      onChange({ upload: "failed" });
      return;
    }
    const done = await expenseClaimsApi
      .finishReceipt(org, started.body.document.id)
      .catch(() => null);
    if (done?.status !== 200) {
      onChange({ upload: "failed" });
      return;
    }
    onChange({
      receipt: { id: done.body.id, name: done.body.name },
      upload: done.body.duplicate ? "duplicate" : "idle",
    });
  };

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="text-sm font-semibold text-fg">
        {fm(fmm.receiptLegend, { n: index + 1 })}
      </legend>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Labelled id={`${ids}-date`} label={fm(fmm.date)}>
          <Input
            id={`${ids}-date`}
            type="date"
            value={line.date}
            onChange={(e) => onChange({ date: e.target.value })}
          />
        </Labelled>
        <Labelled id={`${ids}-merchant`} label={fm(fmm.merchant)}>
          <Input
            id={`${ids}-merchant`}
            value={line.merchant}
            onChange={(e) => onChange({ merchant: e.target.value })}
            autoComplete="organization"
          />
        </Labelled>
        <Labelled id={`${ids}-amount`} label={fm(fmm.amount)}>
          <Input
            id={`${ids}-amount`}
            inputMode="decimal"
            numeric
            prefix="$"
            value={line.amount}
            onChange={(e) => onChange({ amount: e.target.value.replace(/[^0-9.]/g, "") })}
          />
        </Labelled>
      </div>
      <div role="group" aria-labelledby={`${ids}-cat`} className="flex flex-col gap-2">
        <span id={`${ids}-cat`} className="text-sm font-medium text-fg">
          {fm(fmm.category)}
        </span>
        <div className="flex flex-wrap gap-2" data-chips="">
          {chips.map((category) => (
            <Chip
              key={category.id}
              category={category}
              pressed={line.account === category.id}
              onPress={() => onChange({ account: category.id })}
            />
          ))}
        </div>
        {categories.length > CHIP_COUNT ? (
          <select
            aria-label={fm(fmm.moreCategories)}
            className={SELECT}
            value={chosenInMore ? (line.account ?? "") : ""}
            onChange={(e) => onChange({ account: e.target.value || null })}
          >
            <option value="">{fm(fmm.moreCategories)}</option>
            {categories.slice(CHIP_COUNT).map((category) => (
              <option key={category.id} value={category.id}>
                {category.code} {category.name}
              </option>
            ))}
          </select>
        ) : null}
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Labelled id={`${ids}-tax`} label={fm(fmm.taxCode)}>
          <select
            id={`${ids}-tax`}
            className={SELECT}
            value={line.taxCode ?? ""}
            onChange={(e) => onChange({ taxCode: e.target.value || null })}
          >
            <option value="">{fm(fmm.noTax)}</option>
            {(lists?.tax_codes ?? []).map((code) => (
              <option key={code.id} value={code.id}>
                {code.name || code.code}
              </option>
            ))}
          </select>
        </Labelled>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${ids}-file`} className="text-sm font-medium text-fg">
            {fm(fmm.photo)}
          </label>
          <input
            ref={file}
            id={`${ids}-file`}
            type="file"
            accept="image/*,application/pdf"
            capture="environment"
            className="text-sm text-fg file:me-3 file:min-h-touch-target file:rounded-md file:border file:border-border-strong file:bg-surface file:px-3"
            onChange={(e) => {
              const picked = e.target.files?.[0];
              if (picked) void upload(picked);
            }}
          />
          <span className="text-xs text-fg-muted" aria-live="polite" data-upload={line.upload}>
            {line.upload === "uploading"
              ? fm(fmm.uploading)
              : line.upload === "failed"
                ? fm(fmm.uploadFailed)
                : line.upload === "refused"
                  ? fm(fmm.uploadRefused)
                  : line.receipt
                    ? fm(line.upload === "duplicate" ? fmm.duplicate : fmm.attached, {
                        name: line.receipt.name,
                      })
                    : ""}
          </span>
        </div>
      </div>
      <div>
        <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
          {fm(fmm.remove)}
        </Button>
      </div>
    </fieldset>
  );
}

function Chip({
  category,
  pressed,
  onPress,
}: {
  category: Category;
  pressed: boolean;
  onPress: () => void;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onPress}
      className={
        "min-h-touch-target rounded-full border px-3 text-sm " +
        (pressed
          ? "border-border-accent bg-surface-accent text-fg-on-accent"
          : "border-border bg-surface text-fg")
      }
    >
      {category.name}
    </button>
  );
}
