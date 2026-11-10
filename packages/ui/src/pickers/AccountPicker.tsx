"use client";

import { forwardRef, useMemo } from "react";

import { Combobox, type ComboboxOption, type ComboboxProps } from "../primitives/Combobox";

/** Top-level account types of the Canadian chart of accounts (C-01). */
export type AccountType = "asset" | "liability" | "equity" | "revenue" | "expense";

/** Normal balance side of each type. */
export const ACCOUNT_SIDE: Record<AccountType, "debit" | "credit"> = {
  asset: "debit",
  expense: "debit",
  liability: "credit",
  equity: "credit",
  revenue: "credit",
};

export interface PickerAccount {
  id: string;
  code: string;
  name: string;
  type: AccountType;
  /** Sub-type shown under the name, e.g. "Bank", "Current liability". */
  detail?: string;
  archived?: boolean;
}

export interface AccountPickerProps extends Omit<
  ComboboxProps,
  "options" | "value" | "onChange" | "filter"
> {
  accounts: readonly PickerAccount[];
  value: string | null;
  onChange: (accountId: string | null, account: PickerAccount | null) => void;
  /** Only these types (e.g. a sales line: revenue only — expense accounts hidden). */
  types?: readonly AccountType[];
  /** Only accounts whose normal balance is on this side. */
  side?: "debit" | "credit";
  /** Group headings per type, e.g. { asset: "Assets", … } (i18n). */
  typeLabels: Record<AccountType, string>;
}

const TYPE_ORDER: AccountType[] = ["asset", "liability", "equity", "revenue", "expense"];

/**
 * Account picker (A-10-T09): searchable by code or name ("1000", "cheq"), grouped by type in
 * chart order, filtered by allowed types / normal side; archived accounts are never offered.
 */
export const AccountPicker = forwardRef<HTMLInputElement, AccountPickerProps>(
  function AccountPicker({ accounts, value, onChange, types, side, typeLabels, ...props }, ref) {
    const allowed = useMemo(
      () =>
        accounts
          .filter((account) => !account.archived || account.id === value)
          .filter((account) => !types || types.includes(account.type))
          .filter((account) => !side || ACCOUNT_SIDE[account.type] === side)
          .sort(
            (a, b) =>
              TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type) ||
              a.code.localeCompare(b.code, "en-CA", { numeric: true }),
          ),
      [accounts, types, side, value],
    );
    const options = useMemo<ComboboxOption[]>(
      () =>
        allowed.map((account) => ({
          value: account.id,
          label: `${account.code} · ${account.name}`,
          description: account.detail,
          group: typeLabels[account.type],
          keywords: account.code,
        })),
      [allowed, typeLabels],
    );
    return (
      <Combobox
        ref={ref}
        {...props}
        options={options}
        value={value}
        onChange={(id) => onChange(id, allowed.find((account) => account.id === id) ?? null)}
      />
    );
  },
);
