/**
 * Activity heatmap layout (K-09-T24, wireframe A5): the API's days with activity (K-09-T19, days
 * in the organisation's time zone) laid out as a calendar — one column per week (Monday first),
 * one row per weekday — with a shade level 0–4 per day (0 = no activity; 1–4 = quarters of the
 * busiest day), and the month each week starts in for the column labels. Dates are calendar
 * dates ("2026-06-15"), never instants, so no time zone shifts them.
 */

export interface HeatDay {
  date: string;
  count: number;
}

export interface HeatCell {
  date: string;
  count: number;
  level: 0 | 1 | 2 | 3 | 4;
}

export interface HeatWeek {
  /** Seven cells Monday → Sunday; `null` outside the window. */
  days: (HeatCell | null)[];
  /** "2026-06" when the month changes in this week (the column's label), else `null`. */
  month: string | null;
}

const DAY_MS = 86_400_000;

const toUtc = (date: string) =>
  Date.UTC(+date.slice(0, 4), +date.slice(5, 7) - 1, +date.slice(8, 10));
const fromUtc = (ms: number) => new Date(ms).toISOString().slice(0, 10);

/** Shade level of a count against the busiest day. */
export function levelOf(count: number, max: number): HeatCell["level"] {
  if (count <= 0 || max <= 0) return 0;
  return Math.min(4, Math.max(1, Math.ceil((count / max) * 4))) as HeatCell["level"];
}

export function calendar(from: string, to: string, days: readonly HeatDay[]): HeatWeek[] {
  const counts = new Map(days.map((d) => [d.date, d.count]));
  const max = days.reduce((m, d) => Math.max(m, d.count), 0);
  const first = toUtc(from);
  const last = toUtc(to);
  if (Number.isNaN(first) || Number.isNaN(last) || last < first) return [];
  // Monday on or before `from` (getUTCDay: 0 = Sunday).
  const start = first - ((new Date(first).getUTCDay() + 6) % 7) * DAY_MS;
  const weeks: HeatWeek[] = [];
  let month = "";
  for (let monday = start; monday <= last; monday += 7 * DAY_MS) {
    const week: HeatWeek = { days: [], month: null };
    for (let i = 0; i < 7; i += 1) {
      const day = monday + i * DAY_MS;
      if (day < first || day > last) {
        week.days.push(null);
        continue;
      }
      const date = fromUtc(day);
      const count = counts.get(date) ?? 0;
      week.days.push({ date, count, level: levelOf(count, max) });
      if (date.slice(0, 7) !== month) {
        month = date.slice(0, 7);
        if (week.month === null) week.month = month;
      }
    }
    weeks.push(week);
  }
  return weeks;
}
