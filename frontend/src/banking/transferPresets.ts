/**
 * Transfer presets (F-06-T05): "Fund petty cash" (chequing → cash) and "Pay credit card"
 * (chequing → card). Pure functions, no React: the transfer dialog (F-06-T07) shows them as chips
 * and calls `applyTransferPreset` with the accounts it already lists. Same table as the backend
 * (`numo9/banking/transfer_presets.py`): from = the first Chequing, else Savings; to = the first
 * account of the target type; archived accounts never; accounts in name order; a side with no
 * match stays empty for the person to pick.
 */
import type { BankAccount, BankAccountType } from "./api";

export type TransferPresetKey = "fund_petty_cash" | "pay_credit_card";

export interface TransferPreset {
  key: TransferPresetKey;
  from: readonly BankAccountType[];
  to: readonly BankAccountType[];
}

export const TRANSFER_PRESETS: readonly TransferPreset[] = [
  { key: "fund_petty_cash", from: ["chequing", "savings"], to: ["cash"] },
  { key: "pay_credit_card", from: ["chequing", "savings"], to: ["credit_card"] },
];

export interface TransferPrefill {
  from_account: string | null;
  to_account: string | null;
}

type PresetAccount = Pick<BankAccount, "id" | "type" | "display_name" | "archived_at">;

function firstOfTypes(
  accounts: readonly PresetAccount[],
  types: readonly BankAccountType[],
  excludeId: string | null,
): string | null {
  const usable = accounts
    .filter((account) => account.archived_at === null && account.id !== excludeId)
    .slice()
    .sort((a, b) => a.display_name.localeCompare(b.display_name));
  for (const type of types) {
    const found = usable.find((account) => account.type === type);
    if (found) return found.id;
  }
  return null;
}

export function findTransferPreset(key: string): TransferPreset | undefined {
  return TRANSFER_PRESETS.find((preset) => preset.key === key);
}

/** The from/to accounts a preset pre-fills, picked by account type. */
export function applyTransferPreset(
  key: TransferPresetKey,
  accounts: readonly PresetAccount[],
): TransferPrefill {
  const preset = findTransferPreset(key);
  if (!preset) return { from_account: null, to_account: null };
  const from = firstOfTypes(accounts, preset.from, null);
  return { from_account: from, to_account: firstOfTypes(accounts, preset.to, from) };
}

/** Presets that can fill both sides with these accounts (the chips worth showing). */
export function availableTransferPresets(
  accounts: readonly PresetAccount[],
): readonly TransferPreset[] {
  return TRANSFER_PRESETS.filter((preset) => {
    const filled = applyTransferPreset(preset.key, accounts);
    return filled.from_account !== null && filled.to_account !== null;
  });
}
