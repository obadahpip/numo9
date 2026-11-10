/**
 * Calendar-date helpers (A-10-T08/T09). Accounting dates are calendar dates without a time or
 * time zone, carried as ISO strings `YYYY-MM-DD` (the API format) so they never shift a day.
 */
export type IsoDate = string;

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;

/** `YYYY-MM-DD` for a valid calendar date, else null (e.g. 2026-02-30). */
export function isoDate(year: number, month: number, day: number): IsoDate | null {
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) return null;
  if (year < 1 || year > 9999 || month < 1 || month > 12 || day < 1) return null;
  if (day > daysInMonth(year, month)) return null;
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function parseIso(value: IsoDate): { year: number; month: number; day: number } | null {
  const match = ISO.exec(value);
  if (!match) return null;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  return isoDate(year, month, day) ? { year, month, day } : null;
}

export function isIsoDate(value: unknown): value is IsoDate {
  return typeof value === "string" && parseIso(value) !== null;
}

export function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function toUtc(value: IsoDate): Date {
  const parts = parseIso(value);
  if (!parts) throw new RangeError(`Not an ISO date: ${value}`);
  return new Date(Date.UTC(parts.year, parts.month - 1, parts.day));
}

function fromUtc(date: Date): IsoDate {
  return date.toISOString().slice(0, 10);
}

export function addDays(value: IsoDate, days: number): IsoDate {
  const date = toUtc(value);
  date.setUTCDate(date.getUTCDate() + days);
  return fromUtc(date);
}

/** Add months, clamping the day: 31 Jan + 1 month = 28/29 Feb. */
export function addMonths(value: IsoDate, months: number): IsoDate {
  const { year, month, day } = parseIso(value)!;
  const index = year * 12 + (month - 1) + months;
  const nextYear = Math.floor(index / 12);
  const nextMonth = (index % 12) + 1;
  return isoDate(nextYear, nextMonth, Math.min(day, daysInMonth(nextYear, nextMonth)))!;
}

export function startOfMonth(value: IsoDate): IsoDate {
  const { year, month } = parseIso(value)!;
  return isoDate(year, month, 1)!;
}

export function endOfMonth(value: IsoDate): IsoDate {
  const { year, month } = parseIso(value)!;
  return isoDate(year, month, daysInMonth(year, month))!;
}

/** 0 = Sunday … 6 = Saturday. */
export function dayOfWeek(value: IsoDate): number {
  return toUtc(value).getUTCDay();
}

/** Today's calendar date in a time zone (the organisation's, default America/Toronto). */
export function todayIn(timeZone = "America/Toronto", now: Date = new Date()): IsoDate {
  // en-CA formats dates as YYYY-MM-DD.
  return new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

export function compareIso(a: IsoDate, b: IsoDate): number {
  return a < b ? -1 : a > b ? 1 : 0;
}
