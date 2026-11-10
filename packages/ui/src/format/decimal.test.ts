import {
  absDecimal,
  compareDecimals,
  isZeroDecimal,
  subtractDecimals,
  sumDecimals,
} from "./decimal";

describe("exact decimals (A-10-T11 totals)", () => {
  it("sums without float error and ignores empty values", () => {
    expect(sumDecimals(["0.10", "0.20"])).toBe("0.30");
    expect(sumDecimals(Array.from({ length: 1000 }, () => "0.01"))).toBe("10.00");
    expect(sumDecimals(["1250.00", null, undefined, "", "-50.5"])).toBe("1199.50");
    expect(sumDecimals([])).toBe("0.00");
    expect(sumDecimals(["99999999999999.99", "0.01"])).toBe("100000000000000.00");
  });
  it("subtracts, compares, abs, zero", () => {
    expect(subtractDecimals("1200.00", "1250.00")).toBe("-50.00");
    expect(compareDecimals("1.10", "1.1")).toBe(0);
    expect(compareDecimals("-1", "0")).toBe(-1);
    expect(absDecimal("-50.00")).toBe("50.00");
    expect(isZeroDecimal("0.00")).toBe(true);
    expect(isZeroDecimal("-0.01")).toBe(false);
  });
  it("rejects non-decimals and extra precision", () => {
    expect(() => sumDecimals(["1e3"])).toThrow(RangeError);
    expect(() => sumDecimals(["1.005"])).toThrow(RangeError);
    expect(sumDecimals(["1.500"])).toBe("1.50");
  });
});
