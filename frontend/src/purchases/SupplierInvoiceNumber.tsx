"use client";

/**
 * Supplier invoice number with its live check (E-02-T12, gap-24): while typing, the API says
 * whether the number is already on another bill of the same supplier; a taken number shows
 * inline — "Already used on BILL-0042 (12 Sep 2026)" with a link to that bill — and is refused
 * at save. The same number from another supplier is fine.
 */
import { Input } from "@numo9/ui";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useFormatMessage } from "@/i18n";

import { billsApi, type NumberCheck } from "./api";
import { checks, m } from "./messages";

export const CHECK_DEBOUNCE_MS = 300;

export interface SupplierInvoiceNumberProps {
  org: string;
  supplier: string;
  value: string;
  onChange: (value: string) => void;
  exclude?: string;
  id: string;
}

export function SupplierInvoiceNumber({
  org,
  supplier,
  value,
  onChange,
  exclude,
  id,
}: SupplierInvoiceNumberProps) {
  const fm = useFormatMessage();
  const [check, setCheck] = useState<NumberCheck | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    setCheck(null);
    if (!supplier || !value.trim()) return;
    setPending(true);
    let cancelled = false;
    const timer = setTimeout(() => {
      void billsApi.checkNumber(org, supplier, value, exclude).then((result) => {
        if (cancelled) return;
        setPending(false);
        if (result.status === 200 && typeof result.body.available === "boolean")
          setCheck(result.body);
      });
    }, CHECK_DEBOUNCE_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [org, supplier, value, exclude]);

  const taken = check && !check.available ? check.conflict : null;
  return (
    <div className="flex flex-col gap-1 text-sm font-medium text-fg">
      <label htmlFor={id}>{fm(m.supplierInvoiceNo)}</label>
      <Input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        invalid={Boolean(taken)}
        aria-describedby={taken ? `${id}-taken` : undefined}
        autoComplete="off"
      />
      {taken ? (
        <p id={`${id}-taken`} className="text-xs font-medium text-fg-danger" data-number-taken="">
          <span className="me-1">{taken.message}</span>
          <Link href={`/o/${org}/purchases/bills/${taken.id}`} className="underline">
            {fm(checks.open)}
          </Link>
        </p>
      ) : pending && value.trim() && supplier ? (
        <p className="text-xs font-normal text-fg-muted" aria-live="polite">
          {fm(checks.checking)}
        </p>
      ) : null}
    </div>
  );
}
