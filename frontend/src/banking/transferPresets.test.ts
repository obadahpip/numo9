import { describe, expect, it } from "vitest";

import type { BankAccountType } from "./api";
import { applyTransferPreset, availableTransferPresets } from "./transferPresets";

function account(id: string, type: BankAccountType, archived = false) {
  return { id, type, display_name: id, archived_at: archived ? "2026-01-01T00:00:00Z" : null };
}

describe("transfer presets (F-06-T05): pre-fill accounts by type", () => {
  const accounts = [
    account("B Savings", "savings"),
    account("TD Chequing", "chequing"),
    account("Petty Cash", "cash"),
    account("TD Visa", "credit_card"),
  ];

  it("fund petty cash: chequing → cash", () => {
    expect(applyTransferPreset("fund_petty_cash", accounts)).toEqual({
      from_account: "TD Chequing",
      to_account: "Petty Cash",
    });
  });

  it("pay credit card: chequing → card", () => {
    expect(applyTransferPreset("pay_credit_card", accounts)).toEqual({
      from_account: "TD Chequing",
      to_account: "TD Visa",
    });
  });

  it("falls back to savings, skips archived accounts, leaves a missing side empty", () => {
    const few = [account("Old Chequing", "chequing", true), account("RBC Savings", "savings")];
    expect(applyTransferPreset("pay_credit_card", few)).toEqual({
      from_account: "RBC Savings",
      to_account: null,
    });
  });

  it("offers only the presets both sides can fill", () => {
    expect(availableTransferPresets(accounts).map((preset) => preset.key)).toEqual([
      "fund_petty_cash",
      "pay_credit_card",
    ]);
    expect(availableTransferPresets([account("TD Chequing", "chequing")])).toEqual([]);
  });
});
