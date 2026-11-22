import { describe, expect, it } from "vitest";

import discount from "../../../backend/tests/fixtures/documents/calculator_discount.json";
import exclusive from "../../../backend/tests/fixtures/documents/calculator_exclusive.json";
import inclusive from "../../../backend/tests/fixtures/documents/calculator_inclusive.json";
import noTax from "../../../backend/tests/fixtures/documents/calculator_no_tax.json";

import {
  CalculationError,
  allocate,
  calculateDocument,
  documentDiscount,
  type DocInput,
  type DocResult,
} from "./calculator";

interface Fixture extends DocInput {
  name: string;
  expected: DocResult;
}

const cases = (set: unknown): Fixture[] => set as Fixture[];

describe("document calculator mirror (D-01-T10): the backend's fixtures", () => {
  it("has the same 50 exclusive documents as the server", () => {
    expect(cases(exclusive)).toHaveLength(50);
  });

  for (const [label, set] of [
    ["exclusive", exclusive],
    ["inclusive", inclusive],
    ["no tax", noTax],
    ["document discount", discount],
  ] as const) {
    describe(label, () => {
      for (const doc of cases(set)) {
        it(doc.name, () => {
          expect(calculateDocument(doc)).toEqual(doc.expected);
        });
      }
    });
  }
});

describe("rules", () => {
  it("allocates the remainder cents to the largest lines", () => {
    expect(allocate(1000n, [1000n, 1000n, 1000n])).toEqual([334n, 333n, 333n]);
    expect(allocate(0n, [5n])).toEqual([0n]);
    expect(allocate(100n, [0n, -5n, 300n])).toEqual([0n, 0n, 100n]);
    expect(() => allocate(500n, [100n])).toThrow(CalculationError);
  });

  it("caps an amount discount at the lines' total", () => {
    expect(documentDiscount([1000n, 500n], "amount", "100")).toBe(1500n);
    expect(documentDiscount([1000n, 500n], "percent", "50")).toBe(750n);
    expect(() => documentDiscount([1n], "percent", "100.01")).toThrow(CalculationError);
  });

  it("refuses unknown modes and bad discounts", () => {
    expect(() => calculateDocument({ lines: [], tax_mode: "x" as never })).toThrow(
      CalculationError,
    );
    expect(() =>
      calculateDocument({ lines: [{ discount_type: "percent", discount_value: "101" }] }),
    ).toThrow(CalculationError);
  });

  it("splits claimable tax on purchases without changing totals", () => {
    const result = calculateDocument({
      side: "purchase",
      lines: [
        { unit_price: "100", components: [{ key: "hst_on", rate: "13", claimable_pct: "50" }] },
      ],
    });
    expect(result.total).toBe("113.00");
  });
});
