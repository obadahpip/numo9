/**
 * Forgiving input parsers (A-10-T08, Phase 0 UX principle 7).
 *
 * Amounts: `1,234.5`, `1234.50`, `$1 234,50` (fr-CA), `(12.00)`, `-12`, `1.234,56`.
 * Dates: `2026-10-26`, `26/10`, `26/10/2026`, `oct 26`, `26 oct. 2026`, `October 26, 2026`,
 * `today`, `aujourd'hui`, `tomorrow`, `+30`, `-7`, `+2w`, `+1m`.
 * Both return null for input they can't read, so the field can say what is expected.
 */
import { addDays, addMonths, isoDate, parseIso, type IsoDate } from "./dates";
import type { AppLocale } from "./locale";

// ---------------------------------------------------------------------------- money

export interface ParseMoneyOptions {
  locale: AppLocale;
  /** Decimal places kept; more digits than this are an error, not silently rounded. Default 2. */
  fractionDigits?: number;
}

const SPACES = /[\s   ']/g;

/**
 * Read an amount typed by a person; returns a normalised decimal string with `fractionDigits`
 * places (`"1234.50"`, `"-12.00"`) or null.
 *
 * Separators: when both `.` and `,` appear, the last one is the decimal mark. A single kind that
 * appears more than once groups thousands. A single separator followed by exactly 3 digits is a
 * thousands separator where the locale groups with it (`,` in en-CA: `1,234` = 1234); otherwise
 * it is the decimal mark (`1,5` and `1.5` are both 1.50; in fr-CA `1,234` is 1.234 → too many
 * decimals → null).
 */
export function parseMoney(
  input: string,
  { locale, fractionDigits = 2 }: ParseMoneyOptions,
): string | null {
  let text = input.trim();
  if (!text) return null;

  let negative = false;
  if (/^\(.*\)$/.test(text)) {
    negative = true;
    text = text.slice(1, -1);
  }
  text = text.replace(/−/g, "-"); // minus sign
  text = text.replace(/\b(?:CAD|CA|C)\b|\$/gi, "").replace(SPACES, "");
  if (text.startsWith("-")) {
    negative = !negative;
    text = text.slice(1);
  } else if (text.endsWith("-")) {
    negative = !negative;
    text = text.slice(0, -1);
  } else if (text.startsWith("+")) {
    text = text.slice(1);
  }
  if (!/^[\d.,]+$/.test(text) || !/\d/.test(text)) return null;

  const lastDot = text.lastIndexOf(".");
  const lastComma = text.lastIndexOf(",");
  let decimalMark: "." | "," | null = null;
  if (lastDot >= 0 && lastComma >= 0) {
    decimalMark = lastDot > lastComma ? "." : ",";
  } else if (lastDot >= 0 || lastComma >= 0) {
    const mark = lastDot >= 0 ? "." : ",";
    const count = text.split(mark).length - 1;
    const digitsAfter = text.length - text.lastIndexOf(mark) - 1;
    const localeGroups = locale === "fr-CA" ? false : mark === ",";
    if (count > 1) decimalMark = null;
    else if (digitsAfter === 3 && localeGroups) decimalMark = null;
    else decimalMark = mark;
  }

  let integer = text;
  let fraction = "";
  if (decimalMark) {
    const index = text.lastIndexOf(decimalMark);
    integer = text.slice(0, index);
    fraction = text.slice(index + 1);
    if (/[.,]/.test(fraction)) return null;
  }
  const groupMark =
    decimalMark === "." ? "," : decimalMark === "," ? "." : /[.,]/.exec(integer)?.[0];
  if (groupMark) {
    const groups = integer.split(groupMark);
    // Thousands groups: first 1–3 digits, then exactly 3 digits each.
    if (
      groups.length > 1 &&
      !(/^\d{1,3}$/.test(groups[0] ?? "") && groups.slice(1).every((g) => /^\d{3}$/.test(g)))
    ) {
      return null;
    }
    integer = groups.join("");
  }
  if (/[.,]/.test(integer)) return null;
  if (integer === "") integer = "0";
  if (fraction.length > fractionDigits) return null;

  const digits = integer.replace(/^0+(?=\d)/, "");
  const result = fractionDigits > 0 ? `${digits}.${fraction.padEnd(fractionDigits, "0")}` : digits;
  const isZero = !/[1-9]/.test(result);
  return negative && !isZero ? `-${result}` : result;
}

// ---------------------------------------------------------------------------- dates

export interface ParseDateOptions {
  locale: AppLocale;
  /** Today's date in the organisation's time zone (relative words and missing years). */
  today: IsoDate;
}

const MONTHS: [number, string[]][] = [
  [1, ["january", "jan", "janvier", "janv"]],
  [2, ["february", "feb", "fevrier", "fev", "fevr"]],
  [3, ["march", "mar", "mars"]],
  [4, ["april", "apr", "avril", "avr"]],
  [5, ["may", "mai"]],
  [6, ["june", "jun", "juin"]],
  [7, ["july", "jul", "juillet", "juil"]],
  [8, ["august", "aug", "aout"]],
  [9, ["september", "sep", "sept", "septembre"]],
  [10, ["october", "oct", "octobre"]],
  [11, ["november", "nov", "novembre"]],
  [12, ["december", "dec", "decembre"]],
];

function monthFromWord(word: string): number | null {
  for (const [month, names] of MONTHS) if (names.includes(word)) return month;
  // Any unambiguous prefix of 3+ letters: "octo", "septem", "decem".
  if (word.length >= 3) {
    const hits = MONTHS.filter(([, names]) => names.some((name) => name.startsWith(word)));
    if (hits.length === 1) return hits[0]![0];
  }
  return null;
}

const RELATIVE: Record<string, number> = {
  today: 0,
  tod: 0,
  now: 0,
  aujourdhui: 0,
  auj: 0,
  tomorrow: 1,
  tom: 1,
  demain: 1,
  yesterday: -1,
  hier: -1,
};

function normalise(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/['’]/g, "")
    .trim();
}

function fullYear(text: string): number {
  const year = Number(text);
  return text.length <= 2 ? 2000 + year : year;
}

/**
 * Read a date typed by a person; returns `YYYY-MM-DD` or null. Numeric dates are day first
 * (`26/10/2026`), as Canadian documents print them; when the first number can only be a month and
 * the second only a day (`10/26/2026`), they are read month first.
 */
export function parseDate(input: string, { today }: ParseDateOptions): IsoDate | null {
  const text = normalise(input);
  if (!text) return null;
  const base = parseIso(today);
  if (!base) throw new RangeError(`today must be an ISO date, got "${today}"`);

  if (text in RELATIVE) return addDays(today, RELATIVE[text]!);

  // +30, -7, +2w, +1m, +1y (+2s, +1a in French)
  const offset = /^([+-])\s*(\d{1,4})\s*([dwmyjsa])?$/.exec(text);
  if (offset) {
    const amount = Number(offset[2]) * (offset[1] === "-" ? -1 : 1);
    switch (offset[3] ?? "d") {
      case "w":
      case "s":
        return addDays(today, amount * 7);
      case "m":
        return addMonths(today, amount);
      case "y":
      case "a":
        return addMonths(today, amount * 12);
      default:
        return addDays(today, amount);
    }
  }

  // ISO and compact: 2026-10-26, 2026/10/26, 20261026
  const iso =
    /^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/.exec(text) ?? /^(\d{4})(\d{2})(\d{2})$/.exec(text);
  if (iso) return isoDate(Number(iso[1]), Number(iso[2]), Number(iso[3]));

  // Numeric: 26/10, 26/10/2026, 26-10-26, 26.10.2026
  const numeric = /^(\d{1,2})[-/.](\d{1,2})(?:[-/.](\d{2}|\d{4}))?$/.exec(text);
  if (numeric) {
    let day = Number(numeric[1]);
    let month = Number(numeric[2]);
    if (month > 12 && day <= 12) [day, month] = [month, day];
    const year = numeric[3] ? fullYear(numeric[3]) : base.year;
    return isoDate(year, month, day);
  }

  // Day only: "26" → the 26th of the current month.
  if (/^\d{1,2}$/.test(text)) return isoDate(base.year, base.month, Number(text));

  // Words: "oct 26", "26 oct. 2026", "october 26, 2026", "1er octobre 2026"
  const tokens = text
    .replace(/(\d)(er|st|nd|rd|th)\b/g, "$1")
    .split(/[\s,./-]+/)
    .filter(Boolean);
  let month: number | null = null;
  const numbers: string[] = [];
  for (const token of tokens) {
    if (/^\d+$/.test(token)) numbers.push(token);
    else if (month === null) {
      month = monthFromWord(token);
      if (month === null) return null;
    } else return null;
  }
  if (month === null || numbers.length === 0 || numbers.length > 2) return null;
  const [first, second] = numbers;
  let day: number;
  let year = base.year;
  if (second !== undefined) {
    // "26 oct 2026" / "oct 26 2026": the 4-digit (or the later) number is the year.
    if (first!.length === 4) {
      year = Number(first);
      day = Number(second);
    } else {
      day = Number(first);
      year = fullYear(second);
    }
  } else if (first!.length === 4) {
    return null; // "oct 2026" names a month, not a date
  } else {
    day = Number(first);
  }
  return isoDate(year, month, day);
}
