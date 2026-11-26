"use client";

/**
 * Mark as filed and amend (G-03-T12). A reviewed return is marked as filed with the
 * confirmation number the CRA gave (and the day it was filed): the period is then locked for
 * tax — the lock shows on the period in the returns list and the filing timeline. A filed
 * return is amended with a reason: version n + 1 starts as a draft and opens.
 */
import { Button, Dialog, INPUT_BASE, LockIcon, formatDate, type AppLocale } from "@numo9/ui";
import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { useState } from "react";

import { useFormatMessage } from "@/i18n";

import { returnUrl, returnsApi, type TaxReturn } from "./api";
import { retm } from "./messages";

export interface ReturnActionsProps {
  org: string;
  data: TaxReturn;
  onChange: (next: TaxReturn) => void;
}

function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function ReturnActions({ org, data, onChange }: ReturnActionsProps) {
  const fm = useFormatMessage();
  const locale = useLocale() as AppLocale;
  const router = useRouter();
  const [filing, setFiling] = useState(false);
  const [amending, setAmending] = useState(false);
  const [number, setNumber] = useState("");
  const [filedOn, setFiledOn] = useState(today);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  async function file() {
    if (!number.trim()) return setError(fm(retm.required));
    setBusy(true);
    setError("");
    const answer = await returnsApi.file(org, data.id, {
      confirmation_no: number,
      filed_on: filedOn || undefined,
    });
    setBusy(false);
    if (answer.status !== 200) return setError(answer.body?.detail ?? fm(retm.loadFailed));
    setFiling(false);
    setNotice(fm(retm.filed));
    onChange(answer.body);
  }

  async function amend() {
    if (!reason.trim()) return setError(fm(retm.required));
    setBusy(true);
    setError("");
    const answer = await returnsApi.amend(org, data.id, reason);
    setBusy(false);
    if (answer.status !== 201) return setError(answer.body?.detail ?? fm(retm.loadFailed));
    setAmending(false);
    onChange(answer.body);
    router.push(returnUrl(org, answer.body.id));
  }

  const filedReturn = data.status === "filed";
  return (
    <>
      {data.status === "reviewed" && data.is_current ? (
        <Button variant="primary" onClick={() => (setError(""), setFiling(true))}>
          {fm(retm.markFiled)}
        </Button>
      ) : null}
      {filedReturn ? (
        <p className="inline-flex items-center gap-2 text-sm" data-testid="return-filed">
          <span role="img" aria-label={fm(retm.locked)} className="inline-flex">
            <LockIcon />
          </span>
          {fm(retm.filedSummary, {
            date: data.filed_on ? formatDate(data.filed_on, { locale }) : "",
            number: data.confirmation_no,
          })}
        </p>
      ) : null}
      {filedReturn && data.is_current ? (
        <Button onClick={() => (setError(""), setAmending(true))}>{fm(retm.amend)}</Button>
      ) : null}
      {notice ? (
        <p role="status" className="text-sm text-fg-success">
          {notice}
        </p>
      ) : null}

      <Dialog
        open={filing}
        onOpenChange={setFiling}
        title={fm(retm.fileTitle)}
        description={fm(retm.fileIntro)}
        closeLabel={fm(retm.close)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setFiling(false)}>
              {fm(retm.cancel)}
            </Button>
            <Button variant="primary" loading={busy} onClick={() => void file()}>
              {fm(retm.markFiled)}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <label className="flex flex-col text-sm">
            {fm(retm.confirmationNo)}
            <input
              className={INPUT_BASE}
              value={number}
              aria-invalid={error && !number.trim() ? true : undefined}
              onChange={(e) => setNumber(e.target.value)}
            />
          </label>
          <label className="flex flex-col text-sm">
            {fm(retm.filedOn)}
            <input
              type="date"
              className={INPUT_BASE}
              value={filedOn}
              onChange={(e) => setFiledOn(e.target.value)}
            />
          </label>
          {error ? (
            <p role="alert" className="text-sm text-fg-danger">
              {error}
            </p>
          ) : null}
        </div>
      </Dialog>

      <Dialog
        open={amending}
        onOpenChange={setAmending}
        title={fm(retm.amendTitle)}
        description={fm(retm.amendIntro)}
        closeLabel={fm(retm.close)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAmending(false)}>
              {fm(retm.cancel)}
            </Button>
            <Button variant="primary" loading={busy} onClick={() => void amend()}>
              {fm(retm.amend)}
            </Button>
          </>
        }
      >
        <label className="flex flex-col text-sm">
          {fm(retm.amendReason)}
          <textarea
            className={INPUT_BASE}
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
        {error ? (
          <p role="alert" className="mt-2 text-sm text-fg-danger">
            {error}
          </p>
        ) : null}
      </Dialog>
    </>
  );
}
