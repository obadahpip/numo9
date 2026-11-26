/** Shared pieces of the expense claim form (E-04-T09/T10): a form line and a labelled field. */
import type { ReactNode } from "react";

/** One receipt or trip as the form edits it. */
export interface FormLine {
  key: string;
  kind: "receipt" | "mileage";
  date: string;
  merchant: string;
  description: string;
  amount: string;
  account: string | null;
  taxCode: string | null;
  receipt: { id: string; name: string } | null;
  upload: "idle" | "uploading" | "failed" | "refused" | "duplicate";
  fromPlace: string;
  toPlace: string;
  km: string;
}

export function Labelled({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium text-fg">
        {label}
      </label>
      {children}
    </div>
  );
}
