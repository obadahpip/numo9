"use client";

import { forwardRef, useMemo } from "react";

import { Combobox, type ComboboxOption, type ComboboxProps } from "../primitives/Combobox";
import contextRules from "./account-contexts.json";

/** Top-level account types of the Canadian chart of accounts (C-01). */
export type AccountType = "asset" | "liability" | "equity" | "revenue" | "expense";

/** Account sub-types (C-01-T02, backend `AccountSubtype`); the sub-type decides the type. */
export type AccountSubtype =
  | "current_asset"
  | "bank"
  | "inventory"
  | "prepayment"
  | "fixed_asset"
  | "accumulated_amortisation"
  | "non_current_asset"
  | "intangible"
  | "current_liability"
  | "sales_tax_control"
  | "payroll_liability"
  | "non_current_liability"
  | "share_capital"
  | "retained_earnings"
  | "current_year_earnings"
  | "dividends"
  | "other_equity"
  | "revenue"
  | "other_income"
  | "cost_of_sales"
  | "operating_expense"
  | "amortisation"
  | "income_tax"
  | "other_expense";

/**
 * Where the picker is used (C-01-T10). Same rules as the server (`numo9.ledger.contexts`):
 * - `sales` — revenue, other income, current liabilities (deposits); never an expense (gap-07);
 * - `purchase` — expenses and the assets a bill buys;
 * - `journal` — every postable account except Current year earnings;
 * - `bank` — bank accounts only (bank, credit card, line of credit, loan).
 * Sales, purchase and bank never offer accounts the engine posts to by itself (AR, AP, tax
 * controls, payroll liabilities…); sales and purchase never offer bank accounts.
 */
export type AccountContext = "sales" | "purchase" | "journal" | "bank";

interface ContextRule {
  subtypes: readonly string[];
  excludeEngineRoles: boolean;
  bank: "any" | "exclude" | "only";
}

const RULES = contextRules.contexts as Record<AccountContext, ContextRule>;
const ENGINE_ROLES: ReadonlySet<string> = new Set(contextRules.engineRoles);

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
  /** Sub-type (C-01): used by `context` filtering. */
  subtype?: AccountSubtype;
  /** Sub-type shown under the name, e.g. "Bank", "Current liability". */
  detail?: string;
  /** System role (e.g. "ar", "gst_hst_payable") for accounts the engine posts to. */
  systemRole?: string;
  isBank?: boolean;
  /** Level in the chart tree, 1 = top level; sub-accounts are indented under their parent. */
  depth?: number;
  /** False for accounts with sub-accounts: shown for context, can't be chosen (post-to-leaf). */
  postable?: boolean;
  archived?: boolean;
}

export interface AccountPickerProps extends Omit<
  ComboboxProps,
  "options" | "value" | "onChange" | "filter"
> {
  accounts: readonly PickerAccount[];
  value: string | null;
  onChange: (accountId: string | null, account: PickerAccount | null) => void;
  /** Where the picker is used: offers only the accounts that context allows (see above). */
  context?: AccountContext;
  /** Only these types (e.g. a sales line: revenue only — expense accounts hidden). */
  types?: readonly AccountType[];
  /** Only accounts whose normal balance is on this side. */
  side?: "debit" | "credit";
  /** Group headings per type, e.g. { asset: "Assets", … } (i18n). */
  typeLabels: Record<AccountType, string>;
}

const TYPE_ORDER: AccountType[] = ["asset", "liability", "equity", "revenue", "expense"];

/** Whether an account may be offered in a context (mirror of `allowed_in_context`). */
export function allowedInContext(account: PickerAccount, context: AccountContext): boolean {
  const rule = RULES[context];
  if (account.archived) return false;
  if (!account.subtype || !rule.subtypes.includes(account.subtype)) return false;
  if (rule.excludeEngineRoles && account.systemRole && ENGINE_ROLES.has(account.systemRole))
    return false;
  if (rule.bank === "only" && !account.isBank) return false;
  if (rule.bank === "exclude" && account.isBank) return false;
  return true;
}

/**
 * Account picker (A-10-T09, C-01-T10): the one picker every screen uses. Searchable by code or
 * name ("1000", "cheq"), grouped by type in chart order with sub-accounts indented under their
 * parent; filtered by context, allowed types and normal side. Parents (accounts with
 * sub-accounts) are listed but can't be chosen — postings go to leaf accounts; archived accounts
 * are never offered (the current value stays visible).
 */
export const AccountPicker = forwardRef<HTMLInputElement, AccountPickerProps>(
  function AccountPicker(
    { accounts, value, onChange, context, types, side, typeLabels, ...props },
    ref,
  ) {
    const allowed = useMemo(() => {
      const offered = (account: PickerAccount) =>
        (!account.archived || account.id === value) &&
        (!types || types.includes(account.type)) &&
        (!side || ACCOUNT_SIDE[account.type] === side) &&
        (!context ||
          account.id === value ||
          allowedInContext(account, context) ||
          // A parent stays as a heading when one of its sub-accounts is offered.
          account.postable === false);
      const list = accounts.filter(offered);
      // Keep a non-postable parent only if something under it survived the filters.
      const kept = new Set(list.filter((a) => a.postable !== false).map((a) => a.id));
      const byCode = (a: PickerAccount, b: PickerAccount) =>
        TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type) ||
        a.code.localeCompare(b.code, "en-CA", { numeric: true });
      // Chart order: the incoming order when depth is known (server tree order), else by code.
      const ordered = list.some((a) => a.depth !== undefined) ? list : [...list].sort(byCode);
      return ordered.filter((account, index) => {
        if (account.postable !== false) return true;
        const level = account.depth ?? 1;
        for (let i = index + 1; i < ordered.length; i += 1) {
          const next = ordered[i]!;
          if ((next.depth ?? 1) <= level) break;
          if (kept.has(next.id)) return true;
        }
        return false;
      });
    }, [accounts, types, side, context, value]);
    const options = useMemo<ComboboxOption[]>(
      () =>
        allowed.map((account) => ({
          value: account.id,
          label: `${account.code} · ${account.name}`,
          description: account.detail,
          group: typeLabels[account.type],
          keywords: account.code,
          disabled: account.postable === false,
          indent: Math.max(0, (account.depth ?? 1) - 1),
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
