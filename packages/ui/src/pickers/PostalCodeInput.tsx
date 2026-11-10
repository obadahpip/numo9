"use client";

import { forwardRef } from "react";

import { Input, type InputProps } from "../primitives/Input";
import { formatPostalCode } from "./postalCode";

export interface PostalCodeInputProps extends Omit<
  InputProps,
  "value" | "onChange" | "defaultValue"
> {
  value: string;
  onChange: (value: string) => void;
}

/**
 * Postal code input (A-10-T09): upper-cases as you type and inserts the space ("m5v2t6" →
 * "M5V 2T6"); at most 7 characters. Validate with `isValidPostalCode` (message: "Postal code
 * should look like 'M5V 2T6'.").
 */
export const PostalCodeInput = forwardRef<HTMLInputElement, PostalCodeInputProps>(
  function PostalCodeInput({ value, onChange, ...props }, ref) {
    return (
      <Input
        ref={ref}
        {...props}
        value={value}
        onChange={(event) => onChange(formatPostalCode(event.target.value))}
        autoComplete={props.autoComplete ?? "postal-code"}
        autoCapitalize="characters"
        spellCheck={false}
        maxLength={7}
        className="max-w-32 uppercase"
      />
    );
  },
);
