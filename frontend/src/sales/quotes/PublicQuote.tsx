"use client";

/**
 * The public quote page (D-02-T13), `/q/<token>` — what the customer opens from the quote email,
 * without signing in. Mobile-first: the quote (organisation, title, summary, expiry), its lines;
 * **optional lines are checkboxes and each alternative group a set of radio buttons** — ticking
 * one asks the server for the totals with that choice (nothing saved until acceptance) and the
 * totals and deposit update live. Accepting takes the **typed name** (enough on its own — the
 * accessible way) and, optionally, a **drawn signature** on the pad; the big Accept button sends
 * both with the options chosen (D-02-T07 evidence). Decline asks an optional reason. A quote that
 * can't be accepted — **expired** (the reason and "ask for a new quote"), superseded by a
 * revision, already accepted, declined or invoiced, not sent — shows why, and Accept is disabled.
 */
import { Button, ErrorState, Input, Skeleton, formatMoney, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useRef, useState, type PointerEvent } from "react";

import { useFormatMessage } from "@/i18n";

import {
  publicQuoteApi,
  type PublicQuote as Quote,
  type PublicQuoteLine,
  type SelectionTotals,
} from "./api";
import { pm, reasonMessages } from "./publicMessages";

/** The groups of alternative lines, in order of their first line. */
export function groupsOf(lines: readonly PublicQuoteLine[]): [string, PublicQuoteLine[]][] {
  const groups = new Map<string, PublicQuoteLine[]>();
  for (const line of lines) {
    if (!line.alternative_group) continue;
    groups.set(line.alternative_group, [...(groups.get(line.alternative_group) ?? []), line]);
  }
  return [...groups.entries()];
}

/** The selection the page starts from: what the quote says is selected now. */
export function initialSelection(lines: readonly PublicQuoteLine[]): Record<string, boolean> {
  const chosen: Record<string, boolean> = {};
  for (const line of lines) {
    if (line.is_optional || line.alternative_group) chosen[line.id] = line.counted;
  }
  return chosen;
}

export function PublicQuote({ token }: { token: string }) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [gone, setGone] = useState<"missing" | "revoked" | "failed" | null>(null);
  const [selection, setSelection] = useState<Record<string, boolean>>({});
  const [totals, setTotals] = useState<SelectionTotals | null>(null);
  const [name, setName] = useState("");
  const [signature, setSignature] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState("");

  const show = useCallback((loaded: Quote) => {
    setQuote(loaded);
    setSelection(initialSelection(loaded.lines));
    setTotals(null);
  }, []);

  useEffect(() => {
    void publicQuoteApi.get(token).then((result) => {
      if (result.status === 200 && result.body.number) show(result.body);
      else
        setGone(result.status === 410 ? "revoked" : result.status === 404 ? "missing" : "failed");
    });
  }, [token, show]);

  const choose = async (next: Record<string, boolean>) => {
    setSelection(next);
    const answer = await publicQuoteApi.preview(token, next);
    if (answer.status === 200) setTotals(answer.body);
  };

  const accept = async () => {
    if (!quote || busy) return;
    if (!name.trim()) return setProblem(fm(pm.nameRequired));
    setBusy(true);
    setProblem("");
    const result = await publicQuoteApi.accept(token, {
      typed_name: name.trim(),
      signature,
      selections: selection,
    });
    setBusy(false);
    if (result.status === 200 && result.body.number) show(result.body);
    else setProblem(result.body?.detail ?? fm(pm.failed));
  };

  const decline = async () => {
    if (!quote || busy) return;
    setBusy(true);
    const result = await publicQuoteApi.decline(token, reason);
    setBusy(false);
    setDeclining(false);
    if (result.status === 200 && result.body.number) show(result.body);
    else setProblem(result.body?.detail ?? fm(pm.failed));
  };

  if (gone === "failed") {
    return (
      <ErrorState
        title={fm(pm.loadFailed)}
        retryLabel={fm(pm.retry)}
        onRetry={() => window.location.reload()}
      />
    );
  }
  if (gone) {
    return (
      <div className="flex flex-col gap-2" data-public-gone={gone}>
        <h1 className="text-xl font-semibold text-fg">
          {gone === "revoked" ? fm(pm.revoked) : fm(pm.missing)}
        </h1>
        <p className="text-sm text-fg">{fm(pm.askAgain)}</p>
      </div>
    );
  }
  if (!quote) return <Skeleton className="h-96" />;

  const money = (value: string) => formatMoney(value, { locale, currency: quote.currency });
  const shown = totals ?? quote;
  const counted = (line: PublicQuoteLine) =>
    totals?.lines[line.id]?.counted ?? selection[line.id] ?? line.counted;
  const open = quote.can_accept;
  const optional = quote.lines.filter((line) => line.is_optional);
  const groups = groupsOf(quote.lines);
  const deposit = totals?.deposit ?? quote.deposit;

  return (
    <article aria-labelledby={`${ids}-title`} className="flex flex-col gap-5" data-public-quote="">
      <header className="flex flex-col gap-1">
        <p className="text-sm text-fg-muted">{quote.organisation}</p>
        <h1 id={`${ids}-title`} className="text-2xl font-semibold text-fg">
          {quote.title
            ? fm(pm.titled, { number: quote.number, title: quote.title })
            : fm(pm.title, { number: quote.number })}
        </h1>
        <p className="text-sm text-fg">
          {fm(pm.forCustomer, { customer: quote.customer, date: quote.date })}
        </p>
        <p className="text-sm font-medium text-fg">{fm(pm.expires, { date: quote.expiry_date })}</p>
        {quote.summary ? (
          <p className="mt-2 text-sm whitespace-pre-line text-fg">{quote.summary}</p>
        ) : null}
      </header>

      {!open && quote.reason ? (
        <div
          role="status"
          className="rounded-md border border-border-strong bg-surface-info-subtle p-4 text-sm text-fg"
          data-reason={quote.reason}
        >
          <p className="font-semibold">
            {fm(reasonMessages[quote.reason], {
              name: quote.accepted_by ?? "",
              date: quote.expiry_date,
            })}
          </p>
          {quote.reason === "expired" || quote.reason === "superseded" ? (
            <p className="mt-1">{fm(pm.askNew, { organisation: quote.organisation })}</p>
          ) : null}
        </div>
      ) : null}

      <section aria-labelledby={`${ids}-lines`} className="flex flex-col gap-2">
        <h2 id={`${ids}-lines`} className="text-lg font-semibold text-fg">
          {fm(pm.lines)}
        </h2>
        <ul className="flex flex-col divide-y divide-border rounded-md border border-border">
          {quote.lines
            .filter((line) => !line.is_optional && !line.alternative_group)
            .map((line) => (
              <LineRow key={line.id} line={line} money={money} />
            ))}
        </ul>
      </section>

      {optional.length ? (
        <fieldset className="flex flex-col gap-2" disabled={!open}>
          <legend className="text-lg font-semibold text-fg">{fm(pm.options)}</legend>
          {optional.map((line) => (
            <label
              key={line.id}
              className="flex min-h-touch-target items-start gap-3 rounded-md border border-border p-3 text-sm text-fg"
            >
              <input
                type="checkbox"
                className="mt-1 size-5"
                checked={counted(line)}
                onChange={(event) => void choose({ ...selection, [line.id]: event.target.checked })}
              />
              <span className="flex flex-1 flex-col">
                <span className="font-medium">{line.description}</span>
                <span className="text-fg-muted">
                  {fm(pm.lineAmount, { amount: money(line.amount), tax: money(line.tax) })}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
      ) : null}

      {groups.map(([group, members]) => (
        <fieldset key={group} className="flex flex-col gap-2" disabled={!open}>
          <legend className="text-lg font-semibold text-fg">{fm(pm.chooseOne, { group })}</legend>
          {members.map((line) => (
            <label
              key={line.id}
              className="flex min-h-touch-target items-start gap-3 rounded-md border border-border p-3 text-sm text-fg"
            >
              <input
                type="radio"
                name={`${ids}-${group}`}
                className="mt-1 size-5"
                checked={counted(line)}
                onChange={() =>
                  void choose({
                    ...selection,
                    ...Object.fromEntries(members.map((m) => [m.id, m.id === line.id])),
                  })
                }
              />
              <span className="flex flex-1 flex-col">
                <span className="font-medium">{line.description}</span>
                <span className="text-fg-muted">
                  {fm(pm.lineAmount, { amount: money(line.amount), tax: money(line.tax) })}
                </span>
              </span>
            </label>
          ))}
        </fieldset>
      ))}

      <dl
        aria-label={fm(pm.totals)}
        className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 rounded-md bg-surface-subtle p-4 text-sm text-fg"
        aria-live="polite"
      >
        <dt>{fm(pm.subtotal)}</dt>
        <dd className="text-end tabular-nums">{money(shown.subtotal)}</dd>
        {Number(shown.discount_total) ? (
          <>
            <dt>{fm(pm.discount)}</dt>
            <dd className="text-end tabular-nums">{money(`-${shown.discount_total}`)}</dd>
          </>
        ) : null}
        <dt>{fm(pm.tax)}</dt>
        <dd className="text-end tabular-nums">{money(shown.tax_total)}</dd>
        <dt className="text-base font-semibold">{fm(pm.total)}</dt>
        <dd className="text-end text-base font-semibold tabular-nums" data-public-total="">
          {money(shown.total)}
        </dd>
        {Number(deposit) ? (
          <>
            <dt>{fm(pm.deposit)}</dt>
            <dd className="text-end tabular-nums" data-public-deposit="">
              {money(deposit)}
            </dd>
          </>
        ) : null}
      </dl>

      <a
        href={publicQuoteApi.pdfUrl(token)}
        target="_blank"
        rel="noreferrer"
        className="text-sm underline"
      >
        {fm(pm.pdf)}
      </a>

      <section aria-labelledby={`${ids}-accept`} className="flex flex-col gap-3">
        <h2 id={`${ids}-accept`} className="text-lg font-semibold text-fg">
          {fm(pm.acceptHeading)}
        </h2>
        <label className="flex flex-col gap-1 text-sm font-medium text-fg">
          {fm(pm.name)}
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={!open}
            autoComplete="name"
          />
          <span className="text-xs font-normal text-fg-muted">{fm(pm.nameHint)}</span>
        </label>
        <SignaturePad onChange={setSignature} disabled={!open} />
        {problem ? (
          <p role="alert" className="text-sm font-semibold text-fg-danger">
            {problem}
          </p>
        ) : null}
        <Button
          variant="primary"
          className="min-h-14 w-full text-base"
          disabled={!open || busy}
          onClick={() => void accept()}
          data-public-accept=""
        >
          {fm(pm.accept, { total: money(shown.total) })}
        </Button>
        {open ? (
          declining ? (
            <div className="flex flex-col gap-2">
              <label className="flex flex-col gap-1 text-sm font-medium text-fg">
                {fm(pm.declineReason)}
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={3}
                  className="rounded-md border border-border bg-surface p-2 text-sm font-normal text-fg"
                />
              </label>
              <div className="flex gap-2">
                <Button variant="danger" disabled={busy} onClick={() => void decline()}>
                  {fm(pm.confirmDecline)}
                </Button>
                <Button variant="ghost" onClick={() => setDeclining(false)}>
                  {fm(pm.cancel)}
                </Button>
              </div>
            </div>
          ) : (
            <Button variant="ghost" onClick={() => setDeclining(true)}>
              {fm(pm.decline)}
            </Button>
          )
        ) : null}
      </section>
    </article>
  );
}

function LineRow({ line, money }: { line: PublicQuoteLine; money: (v: string) => string }) {
  const fm = useFormatMessage();
  return (
    <li className="flex items-start justify-between gap-3 p-3 text-sm text-fg">
      <span className="flex flex-col">
        <span className="font-medium">{line.description}</span>
        <span className="text-fg-muted">
          {fm(pm.quantity, { quantity: line.quantity, price: money(line.unit_price) })}
        </span>
      </span>
      <span className="text-end tabular-nums">{money(line.amount)}</span>
    </li>
  );
}

/**
 * A drawn signature (optional): pointer, mouse, touch or pen on a canvas; "Clear" starts again.
 * The PNG goes with the acceptance. Typing the name is enough without it — the accessible way.
 */
export function SignaturePad({
  onChange,
  disabled = false,
}: {
  onChange: (png: string) => void;
  disabled?: boolean;
}) {
  const fm = useFormatMessage();
  const ids = useId();
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const drawing = useRef(false);
  const [drawn, setDrawn] = useState(false);

  const point = (event: PointerEvent<HTMLCanvasElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    return { x: event.clientX - box.left, y: event.clientY - box.top };
  };
  const context = () => canvas.current?.getContext("2d") ?? null;

  return (
    <div className="flex flex-col gap-1">
      <span id={`${ids}-label`} className="text-sm font-medium text-fg">
        {fm(pm.signature)}
      </span>
      <canvas
        ref={canvas}
        width={600}
        height={160}
        role="img"
        aria-labelledby={`${ids}-label`}
        aria-describedby={`${ids}-hint`}
        className="h-40 w-full touch-none rounded-md border border-border bg-surface"
        onPointerDown={(event) => {
          if (disabled) return;
          const ctx = context();
          if (!ctx) return;
          drawing.current = true;
          const { x, y } = point(event);
          ctx.lineWidth = 2;
          ctx.lineCap = "round";
          ctx.beginPath();
          ctx.moveTo(x, y);
        }}
        onPointerMove={(event) => {
          if (!drawing.current) return;
          const ctx = context();
          if (!ctx) return;
          const { x, y } = point(event);
          ctx.lineTo(x, y);
          ctx.stroke();
        }}
        onPointerUp={() => {
          if (!drawing.current) return;
          drawing.current = false;
          setDrawn(true);
          onChange(canvas.current?.toDataURL("image/png") ?? "");
        }}
        data-signature-pad=""
      />
      <span id={`${ids}-hint`} className="text-xs text-fg-muted">
        {fm(pm.signatureHint)}
      </span>
      {drawn ? (
        <Button
          variant="ghost"
          size="sm"
          className="self-start"
          onClick={() => {
            const ctx = context();
            if (ctx && canvas.current)
              ctx.clearRect(0, 0, canvas.current.width, canvas.current.height);
            setDrawn(false);
            onChange("");
          }}
        >
          {fm(pm.clearSignature)}
        </Button>
      ) : null}
    </div>
  );
}
