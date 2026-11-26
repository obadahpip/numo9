import { blankLine } from "./ExpenseClaimForm";
import { mileageAmount, priorKm, scaled, splitKm } from "./mileage";

/**
 * E-04-T10 — the calculator matches the server (numo9/purchases/mileage.py): CRA 2026 rates
 * 0.73 / 0.67 after 5,000 km; a trip crossing the threshold is split; cents rounded half to even.
 */
const RATE = { first_tier_rate: "0.73", second_tier_rate: "0.67", tier_threshold_km: 5000 };

test("first tier only", () => {
  expect(mileageAmount("100", RATE)).toEqual({
    amount: "73.00",
    tiers: [{ tier: "first", km: "100.0", rate: "0.73", amount: "73.00" }],
  });
});

test("a trip crossing 5,000 km is split between the two rates", () => {
  const priced = mileageAmount("300", RATE, "4900");
  expect(priced?.tiers).toEqual([
    { tier: "first", km: "100.0", rate: "0.73", amount: "73.00" },
    { tier: "after", km: "200.0", rate: "0.67", amount: "134.00" },
  ]);
  expect(priced?.amount).toBe("207.00");
  expect(mileageAmount("10", RATE, "6000")?.tiers.map((t) => t.tier)).toEqual(["after"]);
});

test("tenths of a kilometre and half-to-even cents, like Decimal.quantize", () => {
  expect(mileageAmount("12.5", RATE)?.amount).toBe("9.12"); // 9.125 → 9.12 (even)
  expect(mileageAmount("13.5", RATE)?.amount).toBe("9.86"); // 9.855 → 9.86 (even)
  expect(mileageAmount("0.1", RATE)?.amount).toBe("0.07"); // 0.073
});

test("nothing for an empty or zero distance", () => {
  expect(mileageAmount("", RATE)).toBeNull();
  expect(mileageAmount("0", RATE)).toBeNull();
  expect(mileageAmount("abc", RATE)).toBeNull();
});

test("helpers", () => {
  expect(scaled("12.34", 4)).toBe(123400);
  expect(scaled("7", 1)).toBe(70);
  expect(splitKm(49000, 3000, 50000)).toEqual([1000, 2000]);
});

test("prior km: other claims this year plus the earlier trips of the form", () => {
  const a = { ...blankLine("mileage"), date: "2026-03-01", km: "100" };
  const b = { ...blankLine("mileage"), date: "2026-03-01", km: "50" };
  const c = { ...blankLine("mileage"), date: "2026-02-01", km: "20" };
  const old = { ...blankLine("mileage"), date: "2025-12-31", km: "999" };
  const receipt = { ...blankLine("receipt"), date: "2026-01-01" };
  const lines = [a, b, c, old, receipt];
  expect(priorKm(a, lines, "4000")).toBe("4020.0"); // c is earlier by date
  expect(priorKm(b, lines, "4000")).toBe("4120.0"); // same date, after a
  expect(priorKm(c, lines, "0")).toBe("0.0");
});
