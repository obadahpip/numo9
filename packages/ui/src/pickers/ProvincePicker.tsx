"use client";

import { forwardRef } from "react";

import type { AppLocale } from "../format/locale";
import { Select, type SelectProps } from "../primitives/Select";
import { PROVINCES } from "./provinces";

export interface ProvincePickerProps extends Omit<SelectProps, "options"> {
  locale: AppLocale;
  /** Headings of the two groups, e.g. { provinces: "Provinces", territories: "Territories" }. */
  groupLabels: { provinces: string; territories: string };
}

/**
 * Province picker (A-10-T09): the 10 provinces and 3 territories, named in the user's language,
 * sorted alphabetically in that language; value is the 2-letter code (ON, QC …). Type-ahead
 * works ("q" → Quebec).
 */
export const ProvincePicker = forwardRef<HTMLButtonElement, ProvincePickerProps>(
  function ProvincePicker({ locale, groupLabels, ...props }, ref) {
    const name = (p: (typeof PROVINCES)[number]) => (locale === "fr-CA" ? p.fr : p.en);
    const collator = new Intl.Collator(locale === "fr-CA" ? "fr-CA" : "en-CA");
    const options = (kind: "province" | "territory") =>
      PROVINCES.filter((p) => p.kind === kind)
        .map((p) => ({ value: p.code, label: name(p) }))
        .sort((a, b) => collator.compare(a.label, b.label));
    return (
      <Select
        ref={ref}
        {...props}
        options={[
          { label: groupLabels.provinces, options: options("province") },
          { label: groupLabels.territories, options: options("territory") },
        ]}
      />
    );
  },
);
