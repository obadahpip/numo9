"use client";

import { forwardRef, useMemo } from "react";

import type { BadgeTone } from "../primitives/Badge";
import { Combobox, type ComboboxOption, type ComboboxProps } from "../primitives/Combobox";

export type TaxCodeSide = "sales" | "purchase";
export type TaxCodeType = "taxable" | "zero_rated" | "exempt" | "out_of_scope";

/** A tax code version as the tax API lists it (G-01-T11). */
export interface PickerTaxCode {
  id: string;
  code: string;
  name: string;
  side: TaxCodeSide;
  type: TaxCodeType;
  effective_from: string;
  effective_to: string | null;
  archived_at?: string | null;
  /** Total rate, e.g. "13" or "14.975". */
  rate?: string;
  /** "GST 5 % · QST 9.975 %" — shown under the name. */
  detail?: string;
}

export interface TaxCodePickerProps extends Omit<
  ComboboxProps,
  "options" | "value" | "onChange" | "filter"
> {
  codes: readonly PickerTaxCode[];
  value: string | null;
  onChange: (id: string | null, code: PickerTaxCode | null) => void;
  /** The document side: a sales line never offers purchase codes, and the reverse (gap-07). */
  side: TaxCodeSide;
  /** The document date (YYYY-MM-DD): only versions in force that day are offered. */
  date: string;
  /** The line account's default code key (G-01-T09): listed first with `defaultLabel`. */
  accountDefault?: string | null;
  /** Type badges (i18n): { taxable: "Taxable", zero_rated: "Zero-rated", … }. */
  typeLabels: Record<TaxCodeType, string>;
  /** Group heading of the account default, e.g. "Account default". */
  defaultLabel: string;
  /** Group heading of the other codes, e.g. "All codes". */
  othersLabel: string;
  /** Under a chosen version that isn't in force on the date, e.g. "Not in force on this date". */
  expiredLabel: string;
}

export const TAX_TYPE_TONES: Record<TaxCodeType, BadgeTone> = {
  taxable: "info",
  zero_rated: "success",
  exempt: "warning",
  out_of_scope: "neutral",
};

/** Whether a code version may be picked on a ``side`` document dated ``date`` (G-01-T08). */
export function taxCodeOffered(code: PickerTaxCode, side: TaxCodeSide, date: string): boolean {
  return (
    code.side === side &&
    !code.archived_at &&
    code.effective_from <= date &&
    (code.effective_to === null || date <= code.effective_to)
  );
}

/**
 * Tax code picker (G-01-T14): the one picker every editor uses (document grid D-01, bills E-02,
 * spend / receive money F-01). It offers only the codes of the document's side that are in force
 * on its date — never a purchase code on a sales line, never an ended rate — with a type badge
 * (Taxable, Zero-rated, Exempt, Out of scope) on each; the line account's default comes first.
 * A stored value that no longer qualifies stays visible, flagged, so the line can be re-picked.
 */
export const TaxCodePicker = forwardRef<HTMLInputElement, TaxCodePickerProps>(
  function TaxCodePicker(
    {
      codes,
      value,
      onChange,
      side,
      date,
      accountDefault,
      typeLabels,
      defaultLabel,
      othersLabel,
      expiredLabel,
      ...props
    },
    ref,
  ) {
    const offered = useMemo(
      () => codes.filter((code) => taxCodeOffered(code, side, date) || code.id === value),
      [codes, side, date, value],
    );
    const options = useMemo<ComboboxOption[]>(() => {
      const first = offered.filter((c) => accountDefault && c.code === accountDefault);
      const rest = offered.filter((c) => !first.includes(c));
      const option = (code: PickerTaxCode, group: string): ComboboxOption => {
        const stale = !taxCodeOffered(code, side, date);
        return {
          value: code.id,
          label: code.name,
          description: stale ? expiredLabel : code.detail,
          group,
          keywords: `${code.code} ${code.rate ?? ""}`,
          badge: { label: typeLabels[code.type], tone: TAX_TYPE_TONES[code.type] },
          disabled: stale && code.id !== value,
        };
      };
      return [
        ...first.map((c) => option(c, defaultLabel)),
        ...rest.map((c) => option(c, first.length ? othersLabel : "")),
      ].map((o) => (o.group ? o : { ...o, group: undefined }));
    }, [
      offered,
      accountDefault,
      side,
      date,
      typeLabels,
      defaultLabel,
      othersLabel,
      expiredLabel,
      value,
    ]);
    return (
      <Combobox
        ref={ref}
        {...props}
        options={options}
        value={value}
        onChange={(id) => onChange(id, offered.find((code) => code.id === id) ?? null)}
      />
    );
  },
);
