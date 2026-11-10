/**
 * Display formatters (A-10-T08) — the one date, time and money format per locale (gap-01, gap-44):
 *
 * | | en-CA | fr-CA |
 * |---|---|---|
 * | Date | `26 Oct 2026` | `26 oct. 2026` |
 * | Time (12 h / 24 h per user) | `4:33 p.m.` / `16:33` | `4 h 33 p.m.` / `16 h 33` |
 * | Money | `$1,234.56` | `1 234,56 $` |
 *
 * Amounts are decimal strings from the API (`"1234.56"`) and are formatted without passing
 * through binary floating point.
 */
import { parseIso, type IsoDate } from "./dates";
import {
  DEFAULT_TIME_ZONE,
  defaultTimeFormat,
  intlLocale,
  type AppLocale,
  type TimeFormat,
} from "./locale";

export type Amount = string | number | bigint;

const DECIMAL = /^-?\d+(\.\d+)?$/;

export interface MoneyOptions {
  locale: AppLocale;
  /** ISO 4217 code; default CAD. Other currencies show their code/symbol (US$, € …). */
  currency?: string;
  /** Negative amounts in parentheses, as on financial statements: ($1,234.56). */
  accounting?: boolean;
  /** Decimal places; default 2. */
  fractionDigits?: number;
}

const numberFormats = new Map<string, Intl.NumberFormat>();

function moneyFormat(options: MoneyOptions): Intl.NumberFormat {
  const currency = options.currency ?? "CAD";
  const digits = options.fractionDigits ?? 2;
  const key = `${intlLocale(options.locale)}|${currency}|${options.accounting ? 1 : 0}|${digits}`;
  let format = numberFormats.get(key);
  if (!format) {
    format = new Intl.NumberFormat(intlLocale(options.locale), {
      style: "currency",
      currency,
      currencySign: options.accounting ? "accounting" : "standard",
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
    numberFormats.set(key, format);
  }
  return format;
}

function toDecimalString(amount: Amount): string {
  if (typeof amount === "bigint") return amount.toString();
  if (typeof amount === "number") {
    if (!Number.isFinite(amount)) throw new RangeError(`Not a finite amount: ${amount}`);
    return String(amount);
  }
  const trimmed = amount.trim();
  if (!DECIMAL.test(trimmed)) throw new RangeError(`Not a decimal amount: "${amount}"`);
  return trimmed;
}

/** `$1,234.56` (en-CA), `1 234,56 $` (fr-CA). Zero shows as `$0.00`, never blank. */
export function formatMoney(amount: Amount, options: MoneyOptions): string {
  const value = toDecimalString(amount);
  // Intl formats decimal strings exactly (no float rounding of "0.1 + 0.2" kinds).
  const format = moneyFormat(options);
  const formatted = format.format(value as unknown as number);
  // A negative amount that rounds to zero shows as $0.00, never "-$0.00" or "($0.00)".
  if (value.startsWith("-") && !/[1-9]/.test(formatted)) {
    return format.format(value.slice(1) as unknown as number);
  }
  return formatted;
}

/** A plain number in the locale: `1,234.5` / `1 234,5` (quantities, rates). */
export function formatNumber(
  value: Amount,
  { locale, maximumFractionDigits = 4 }: { locale: AppLocale; maximumFractionDigits?: number },
): string {
  return new Intl.NumberFormat(intlLocale(locale), { maximumFractionDigits }).format(
    toDecimalString(value) as unknown as number,
  );
}

export interface DateOptions {
  locale: AppLocale;
  /** For `Date` values (instants): the time zone to show them in. Default America/Toronto. */
  timeZone?: string;
}

/**
 * `26 Oct 2026` (en-CA), `26 oct. 2026` (fr-CA). ISO date strings are calendar dates and never
 * shift; `Date` instants are shown in `timeZone`.
 */
export function formatDate(value: IsoDate | Date, { locale, timeZone }: DateOptions): string {
  let date: Date;
  let zone: string;
  if (typeof value === "string") {
    const parts = parseIso(value);
    if (!parts) throw new RangeError(`Not an ISO date: "${value}"`);
    date = new Date(Date.UTC(parts.year, parts.month - 1, parts.day));
    zone = "UTC";
  } else {
    date = value;
    zone = timeZone ?? DEFAULT_TIME_ZONE;
  }
  const parts = new Intl.DateTimeFormat(intlLocale(locale), {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: zone,
  }).formatToParts(date);
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value ?? "";
  // Day-month-year in both locales (en-CA's Intl default is "Oct 26, 2026").
  return `${get("day")} ${get("month")} ${get("year")}`;
}

export interface TimeOptions {
  locale: AppLocale;
  /** The user's preference (A-02-T01 `time_format`); default 12 h in English, 24 h in French. */
  timeFormat?: TimeFormat;
  timeZone?: string;
}

/** `4:33 p.m.` / `16:33` (en-CA), `4 h 33 p.m.` / `16 h 33` (fr-CA). Never "16:33PM" (gap-44). */
export function formatTime(
  value: Date | string,
  { locale, timeFormat, timeZone }: TimeOptions,
): string {
  const date = typeof value === "string" ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) throw new RangeError(`Not a date-time: "${String(value)}"`);
  const format = timeFormat ?? defaultTimeFormat(locale);
  return new Intl.DateTimeFormat(intlLocale(locale), {
    hour: "numeric",
    minute: "2-digit",
    hourCycle: format === "24h" ? "h23" : "h12",
    timeZone: timeZone ?? DEFAULT_TIME_ZONE,
  }).format(date);
}

/** `26 Oct 2026, 4:33 p.m.` / `26 oct. 2026, 16 h 33` (audit log, history). */
export function formatDateTime(value: Date | string, options: TimeOptions): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return `${formatDate(date, options)}, ${formatTime(date, options)}`;
}
