"use client";

/**
 * Invoice email composer (D-03a-T15), `/o/:org/sales/invoices/:id/email`: the recipients (the
 * customer's people marked "include in emails" to start with), subject and message in the
 * customer's language, the attached PDF with an inline preview (the same PDF the customer gets),
 * Send, and the earlier sends with whether the customer has viewed the invoice (D-03a-T12).
 */
import { Badge, Button, ErrorState, formatDate, Input, type AppLocale } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState, type FormEvent } from "react";

import { useFormatMessage } from "@/i18n";

import { invoiceEmailApi, parseRecipients, type InvoiceEmailDefaults } from "./api";
import { em } from "./messages";

export function InvoiceEmailComposer({ org, id }: Readonly<{ org: string; id: string }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const ids = useId();
  const [data, setData] = useState<InvoiceEmailDefaults | null>(null);
  const [failed, setFailed] = useState(false);
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [preview, setPreview] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfFailed, setPdfFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState<{ to?: string; subject?: string }>({});

  const load = useCallback(
    (fill: boolean) =>
      invoiceEmailApi
        .defaults(org, id)
        .then((result) => {
          if (result.status !== 200) return setFailed(true);
          setData(result.body);
          if (fill) {
            setTo(result.body.to.join(", "));
            setSubject(result.body.subject);
            setMessage(result.body.message);
          }
        })
        .catch(() => setFailed(true)),
    [org, id],
  );
  useEffect(() => {
    void load(true);
  }, [load]);

  useEffect(() => {
    if (!preview || pdfUrl) return;
    let live = true;
    void invoiceEmailApi.pdfBlobUrl(org, id).then((url) => {
      if (!live) {
        if (url) URL.revokeObjectURL(url);
        return;
      }
      setPdfFailed(url === null);
      setPdfUrl(url);
    });
    return () => {
      live = false;
    };
  }, [preview, pdfUrl, org, id]);
  useEffect(
    () => () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    },
    [pdfUrl],
  );

  const date = (value: string) => formatDate(value.slice(0, 10), { locale });

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const { valid, invalid } = parseRecipients(to);
    const errors: { to?: string; subject?: string } = {};
    if (invalid.length) errors.to = fm(em.invalid, { addresses: invalid.join(", ") });
    else if (!valid.length) errors.to = fm(em.noRecipient);
    if (!subject.trim()) errors.subject = fm(em.subjectRequired);
    setFieldError(errors);
    if (errors.to || errors.subject) return;
    setBusy(true);
    setError("");
    const result = await invoiceEmailApi
      .send(org, id, { to: valid, subject: subject.trim(), message })
      .catch(() => null);
    setBusy(false);
    if (result?.status === 201) {
      setNotice(fm(em.sent, { to: valid.join(", ") }));
      void load(false);
      return;
    }
    const refusal = result?.body as { detail?: string } | undefined;
    setError(fm(em.failed, { reason: refusal?.detail ?? "" }));
  };

  if (failed)
    return (
      <ErrorState
        title={fm(em.loadFailed)}
        retryLabel={fm(em.retry)}
        onRetry={() => {
          setFailed(false);
          void load(true);
        }}
      />
    );
  if (!data) return null;

  return (
    <div className="flex flex-col gap-6 lg:flex-row" data-invoice-email="">
      <form className="flex flex-1 flex-col gap-4" onSubmit={(e) => void submit(e)} noValidate>
        <h1 className="text-xl font-semibold text-fg">{fm(em.title)}</h1>
        {!data.sendable ? (
          <p role="note" className="rounded-md border border-border p-3 text-sm">
            {fm(em.notSendable)}
          </p>
        ) : null}
        <div className="flex flex-col gap-1 text-sm">
          <label htmlFor={`${ids}-to`} className="font-medium">
            {fm(em.to)}
          </label>
          <Input
            id={`${ids}-to`}
            value={to}
            onChange={(e) => setTo(e.target.value)}
            aria-describedby={`${ids}-to-hint${fieldError.to ? ` ${ids}-to-error` : ""}`}
            aria-invalid={fieldError.to ? true : undefined}
          />
          <span id={`${ids}-to-hint`} className="text-fg-muted">
            {fm(em.toHint)}
          </span>
          {fieldError.to ? (
            <span id={`${ids}-to-error`} className="text-fg-danger">
              {fieldError.to}
            </span>
          ) : null}
        </div>
        <div className="flex flex-col gap-1 text-sm">
          <label htmlFor={`${ids}-subject`} className="font-medium">
            {fm(em.subject)}
          </label>
          <Input
            id={`${ids}-subject`}
            value={subject}
            maxLength={300}
            onChange={(e) => setSubject(e.target.value)}
            aria-describedby={fieldError.subject ? `${ids}-subject-error` : undefined}
            aria-invalid={fieldError.subject ? true : undefined}
          />
          {fieldError.subject ? (
            <span id={`${ids}-subject-error`} className="text-fg-danger">
              {fieldError.subject}
            </span>
          ) : null}
        </div>
        <div className="flex flex-col gap-1 text-sm">
          <label htmlFor={`${ids}-message`} className="font-medium">
            {fm(em.message)}
          </label>
          <textarea
            id={`${ids}-message`}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={8}
            maxLength={5000}
            className="w-full rounded-md border border-border bg-surface p-2 text-sm text-fg"
          />
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span data-attachment="">{fm(em.attachment, { file: data.file_name })}</span>
          <Button
            type="button"
            onClick={() => setPreview((shown) => !shown)}
            aria-expanded={preview}
            aria-controls={`${ids}-preview`}
          >
            {fm(preview ? em.hidePreview : em.showPreview)}
          </Button>
        </div>
        {error ? (
          <p role="alert" className="text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
        <p role="status" className="text-sm text-fg-muted">
          {notice}
        </p>
        <div>
          <Button type="submit" variant="primary" loading={busy} disabled={!data.sendable || busy}>
            {fm(busy ? em.sending : em.send)}
          </Button>
        </div>
        {data.sends.length > 0 ? (
          <section className="flex flex-col gap-2">
            <h2 className="text-sm font-semibold">{fm(em.history)}</h2>
            <ul className="flex flex-col gap-1 text-sm" data-sends="">
              {data.sends.map((row) => (
                <li key={row.id} className="flex flex-wrap items-center gap-2">
                  <span>
                    {fm(em.historyLine, {
                      date: date(row.sent_at),
                      to: row.recipients.join(", "),
                    })}
                  </span>
                  <Badge tone={row.viewed_at ? "success" : "neutral"}>
                    {row.viewed_at
                      ? fm(em.viewed, { date: date(row.viewed_at) })
                      : fm(em.notViewed)}
                  </Badge>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </form>
      <div id={`${ids}-preview`} className="flex-1" hidden={!preview}>
        {preview && pdfUrl ? (
          <iframe
            title={fm(em.previewTitle)}
            src={pdfUrl}
            className="h-[80vh] w-full rounded-md border border-border"
          />
        ) : null}
        {preview && pdfFailed ? (
          <p role="alert" className="text-sm text-fg-danger">
            {fm(em.previewFailed)}
          </p>
        ) : null}
      </div>
    </div>
  );
}
