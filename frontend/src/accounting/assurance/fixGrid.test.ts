import { describe, expect, it } from "vitest";

import { emptyGridLine, gridFromFix, gridPayload, gridProblem, gridTotals } from "./fixGrid";

/**
 * K-09-T22 — the proposed-fix drawer's editable grid: the proposal's lines become rows (zero
 * amounts blank), totals are exact, a draft needs two filled lines that balance, and the payload
 * carries the edited rows only.
 */
const FIX = {
  lines: [
    {
      account: "acc-1000",
      code: "1000",
      label: "1000 · Petty Cash",
      debit: "994.17",
      credit: "0.00",
      description: "",
    },
    {
      account: "acc-2900",
      code: "2900",
      label: "2900 · Shareholder Loan",
      debit: "0.00",
      credit: "994.17",
      description: "",
    },
  ],
};

describe("fix grid", () => {
  it("loads the proposal and is balanced", () => {
    const lines = gridFromFix(FIX);
    expect(lines.map((l) => [l.account, l.debit, l.credit])).toEqual([
      ["acc-1000", "994.17", ""],
      ["acc-2900", "", "994.17"],
    ]);
    expect(gridTotals(lines)).toEqual({
      debit: "994.17",
      credit: "994.17",
      difference: "0.00",
      balanced: true,
    });
    expect(gridProblem(lines)).toBeNull();
  });

  it("reports the difference exactly and refuses an unbalanced or invalid grid", () => {
    const lines = gridFromFix(FIX);
    lines[1] = { ...lines[1]!, credit: "900.10" };
    expect(gridTotals(lines).difference).toBe("94.07");
    expect(gridProblem(lines)).toBe("balance");
    lines[1] = { ...lines[1]!, credit: "-5" };
    expect(gridProblem(lines)).toBe("amount");
    lines[1] = { ...lines[1]!, credit: "1.234" };
    expect(gridProblem(lines)).toBe("amount");
    expect(gridProblem([gridFromFix(FIX)[0]!, emptyGridLine()])).toBe("lines");
  });

  it("sends the filled rows only, blank amounts as zero", () => {
    const lines = [...gridFromFix(FIX), emptyGridLine()];
    lines[0] = { ...lines[0]!, description: "  Owner paid  " };
    expect(gridPayload(lines)).toEqual([
      { account: "acc-1000", debit: "994.17", credit: "0", description: "Owner paid" },
      { account: "acc-2900", debit: "0", credit: "994.17", description: "" },
    ]);
  });
});
