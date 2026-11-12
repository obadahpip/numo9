import { describe, expect, it } from "vitest";

import { DEFAULT_PRESET, presetOf, presetRange } from "./presets";

/** A-04-T09 — date presets of the audit log viewer. */
describe("presetRange", () => {
  const today = "2026-11-12";

  it("ends every preset today", () => {
    expect(presetRange("today", today)).toEqual({ from: today, to: today });
    expect(presetRange("last7", today)).toEqual({ from: "2026-11-06", to: today });
    expect(presetRange("last30", today)).toEqual({ from: "2026-10-14", to: today });
    expect(presetRange("thisMonth", today)).toEqual({ from: "2026-11-01", to: today });
    expect(presetRange("thisQuarter", today)).toEqual({ from: "2026-10-01", to: today });
  });

  it("defaults to the last 90 days, like the API", () => {
    expect(DEFAULT_PRESET).toBe("last90");
    expect(presetRange("last90", today)).toEqual({ from: "2026-08-15", to: today });
  });

  it("follows the fiscal year end", () => {
    expect(presetRange("thisFiscalYear", today)).toEqual({ from: "2026-01-01", to: today });
    expect(presetRange("thisFiscalYear", today, { month: 3, day: 31 })).toEqual({
      from: "2026-04-01",
      to: today,
    });
    expect(presetRange("thisFiscalYear", "2026-02-10", { month: 3, day: 31 })).toEqual({
      from: "2025-04-01",
      to: "2026-02-10",
    });
    // 28/29 February year ends.
    expect(presetRange("thisFiscalYear", "2028-03-05", { month: 2, day: 29 })).toEqual({
      from: "2028-03-01",
      to: "2028-03-05",
    });
    expect(presetRange("thisFiscalYear", "2027-03-05", { month: 2, day: 29 })).toEqual({
      from: "2027-03-01",
      to: "2027-03-05",
    });
  });

  it("names the preset of a range, or custom", () => {
    expect(presetOf({ from: "2026-11-06", to: today }, today)).toBe("last7");
    expect(presetOf({ from: "2026-09-01", to: "2026-09-30" }, today)).toBe("custom");
  });
});
