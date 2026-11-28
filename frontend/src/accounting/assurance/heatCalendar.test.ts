import { describe, expect, it } from "vitest";

import { calendar, levelOf } from "./heatCalendar";

/** K-09-T24 — heatmap calendar: weeks Monday first, every day of the window once, counts as the
 * API gave them (= the audit log), shade levels by quarter of the busiest day. */
describe("heatmap calendar", () => {
  it("lays the window out in Monday-first weeks with the API's counts", () => {
    // 3 Jun 2026 is a Wednesday; 15 Jun a Monday.
    const weeks = calendar("2026-06-03", "2026-06-16", [
      { date: "2026-06-15", count: 12 },
      { date: "2026-06-03", count: 3 },
    ]);
    expect(weeks).toHaveLength(3);
    expect(weeks[0]!.days.slice(0, 2)).toEqual([null, null]);
    expect(weeks[0]!.days[2]).toEqual({ date: "2026-06-03", count: 3, level: 1 });
    expect(weeks[0]!.month).toBe("2026-06");
    expect(weeks[2]!.days[0]).toEqual({ date: "2026-06-15", count: 12, level: 4 });
    expect(weeks[2]!.days.slice(2)).toEqual([null, null, null, null, null]);
    const cells = weeks.flatMap((w) => w.days).filter(Boolean);
    expect(cells).toHaveLength(14);
    expect(cells.reduce((n, c) => n + c!.count, 0)).toBe(15); // the total of the API
  });

  it("labels the week a month starts in", () => {
    const weeks = calendar("2026-06-29", "2026-07-12", []);
    expect(weeks.map((w) => w.month)).toEqual(["2026-06", null]);
    expect(weeks[0]!.days.find((c) => c?.date === "2026-07-01")?.level).toBe(0);
  });

  it("shades by quarter of the busiest day", () => {
    expect([0, 1, 3, 5, 6, 8, 12].map((n) => levelOf(n, 12))).toEqual([0, 1, 1, 2, 2, 3, 4]);
    expect(levelOf(5, 0)).toBe(0);
    expect(calendar("2026-06-10", "2026-06-01", [])).toEqual([]);
  });
});
