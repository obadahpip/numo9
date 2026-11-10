"use client";

import { forwardRef, useEffect, useState } from "react";

import type { AppLocale } from "../format/locale";
import { parseMoney } from "../format/parse";
import { Input, type InputProps } from "../primitives/Input";

export interface CurrencyInputProps extends Omit<
  InputProps,
  "value" | "onChange" | "defaultValue" | "prefix" | "suffix" | "numeric"
> {
  /** Decimal string ("1234.50") or null when empty. */
  value: string | null;
  onChange: (value: string | null) => void;
  locale: AppLocale;
  /** ISO code shown after the amount; default CAD. */
  currency?: string;
  /** Shown under the input when the text isn't an amount. */
  unreadableMessage: string;
  fractionDigits?: number;
}

function display(value: string | null, locale: AppLocale, fractionDigits: number): string {
  if (value === null) return "";
  return new Intl.NumberFormat(locale === "fr-CA" ? "fr-CA" : "en-CA", {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value as unknown as number);
}

/**
 * Money input (A-10-T09): accepts forgiving amounts (`1,234.5`, `$1 234,50`, `(12)`), shows them
 * formatted for the locale after leaving the field, right-aligned with the currency code. The
 * value is a decimal string — never a float.
 */
export const CurrencyInput = forwardRef<HTMLInputElement, CurrencyInputProps>(
  function CurrencyInput(
    {
      value,
      onChange,
      locale,
      currency = "CAD",
      unreadableMessage,
      fractionDigits = 2,
      id,
      onBlur,
      ...props
    },
    ref,
  ) {
    const [text, setText] = useState(() => display(value, locale, fractionDigits));
    const [unreadable, setUnreadable] = useState(false);

    useEffect(() => {
      setText(display(value, locale, fractionDigits));
      setUnreadable(false);
    }, [value, locale, fractionDigits]);

    const commit = () => {
      if (!text.trim()) {
        setUnreadable(false);
        if (value !== null) onChange(null);
        return;
      }
      const parsed = parseMoney(text, { locale, fractionDigits });
      if (parsed === null) {
        setUnreadable(true);
        return;
      }
      setUnreadable(false);
      if (parsed === value) setText(display(value, locale, fractionDigits));
      else onChange(parsed);
    };

    const messageId = id ? `${id}-unreadable` : undefined;
    return (
      <div className="grid gap-1">
        <Input
          ref={ref}
          id={id}
          {...props}
          numeric
          inputMode="decimal"
          autoComplete="off"
          suffix={currency}
          value={text}
          invalid={props.invalid || unreadable}
          aria-describedby={
            [props["aria-describedby"], unreadable ? messageId : null].filter(Boolean).join(" ") ||
            undefined
          }
          onChange={(event) => setText(event.target.value)}
          onBlur={(event) => {
            commit();
            onBlur?.(event);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") commit();
            props.onKeyDown?.(event);
          }}
        />
        {unreadable ? (
          <p id={messageId} className="text-sm font-medium text-fg-danger">
            {unreadableMessage}
          </p>
        ) : null}
      </div>
    );
  },
);
