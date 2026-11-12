/**
 * Date presets of the audit log viewer (A-04-T09): Today, Last 7 / 30 / 90 days, This month,
 * This quarter, This fiscal year, or a custom range. Ranges are calendar dates in the
 * organisation's time zone and end today (nothing is logged in the future). "Last 90 days" is the
 * API's default range (A-04-T07).
 */
import { addDays, isoDate, parseIso, type IsoDate } from "@numo9/ui";

export const PRESETS = [
  "today",
  "last7",
  "last30",
  "last90",
  "thisMonth",
  "thisQuarter",
  "thisFiscalYear",
  "custom",
] as const;
export type Preset = (typeof PRESETS)[number];
export const DEFAULT_PRESET: Exclude<Preset, "custom"> = "last90";

export interface DateRange {
  from: IsoDate;
  to: IsoDate;
}

/** Fiscal year end as month/day; default 31 December (organisation settings arrive with A-05). */
export interface FiscalYearEnd {
  month: number;
  day: number;
}
export const CALENDAR_YEAR_END: FiscalYearEnd = { month: 12, day: 31 };

function parts(value: IsoDate) {
  const p = parseIso(value);
  if (!p) throw new RangeError(`Not an ISO date: "${value}"`);
  return p;
}

/** The fiscal year end on or after `day`'s year-end in `year`, clamped to the month's length. */
function yearEnd(year: number, end: FiscalYearEnd): IsoDate {
  for (let day = end.day; day >= 28; day -= 1) {
    const value = isoDate(year, end.month, day);
    if (value) return value;
  }
  return isoDate(year, end.month, 28)!;
}

export function presetRange(
  preset: Exclude<Preset, "custom">,
  today: IsoDate,
  fiscalYearEnd: FiscalYearEnd = CALENDAR_YEAR_END,
): DateRange {
  const { year, month } = parts(today);
  switch (preset) {
    case "today":
      return { from: today, to: today };
    case "last7":
      return { from: addDays(today, -6), to: today };
    case "last30":
      return { from: addDays(today, -29), to: today };
    case "last90":
      return { from: addDays(today, -89), to: today };
    case "thisMonth":
      return { from: isoDate(year, month, 1)!, to: today };
    case "thisQuarter":
      return { from: isoDate(year, Math.floor((month - 1) / 3) * 3 + 1, 1)!, to: today };
    case "thisFiscalYear": {
      const endThisYear = yearEnd(year, fiscalYearEnd);
      const previousEnd = today <= endThisYear ? yearEnd(year - 1, fiscalYearEnd) : endThisYear;
      return { from: addDays(previousEnd, 1), to: today };
    }
  }
}

/** The preset a range corresponds to (for showing the current filter), else "custom". */
export function presetOf(
  range: DateRange,
  today: IsoDate,
  fiscalYearEnd: FiscalYearEnd = CALENDAR_YEAR_END,
): Preset {
  for (const preset of PRESETS) {
    if (preset === "custom") continue;
    const candidate = presetRange(preset, today, fiscalYearEnd);
    if (candidate.from === range.from && candidate.to === range.to) return preset;
  }
  return "custom";
}
