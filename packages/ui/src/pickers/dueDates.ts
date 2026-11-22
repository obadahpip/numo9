/**
 * Due dates from payment terms (D-01-T17): the client mirror of
 * `numo9.documents.due_dates.due_date` — the four term types of the terms master (B-01-T05).
 */
import { addDays, daysInMonth, endOfMonth, isoDate, parseIso, type IsoDate } from "../format/dates";

export type TermsType =
  | "days_after_document"
  | "days_after_month_end"
  | "day_of_following_month"
  | "day_of_current_month";

export interface PaymentTermOption {
  id: string;
  /** "Net 30", "EOM", "Due on receipt" (i18n, from the terms master). */
  name: string;
  terms_type: TermsType;
  days: number;
}

function dayOf(year: number, month: number, n: number): IsoDate {
  return isoDate(year, month, Math.min(Math.max(n, 1), daysInMonth(year, month)))!;
}

function nextMonth(year: number, month: number): [number, number] {
  return month === 12 ? [year + 1, 1] : [year, month + 1];
}

/** The due date of a document dated `date` under `terms_type` / `days`. */
export function dueDate(date: IsoDate, termsType: TermsType, days: number): IsoDate {
  const parts = parseIso(date);
  if (!parts || days < 0) throw new RangeError(`Can't work out a due date from ${date}.`);
  const { year, month } = parts;
  switch (termsType) {
    case "days_after_document":
      return addDays(date, days);
    case "days_after_month_end":
      return addDays(endOfMonth(date), days);
    case "day_of_following_month":
      return dayOf(...nextMonth(year, month), days);
    case "day_of_current_month": {
      const thisMonth = dayOf(year, month, days);
      return thisMonth >= date ? thisMonth : dayOf(...nextMonth(year, month), days);
    }
  }
}

/** Whole days from `date` to `due` (negative when overdue). */
export function daysBetween(date: IsoDate, due: IsoDate): number {
  const utc = (value: IsoDate) => {
    const { year, month, day } = parseIso(value)!;
    return Date.UTC(year, month - 1, day);
  };
  return Math.round((utc(due) - utc(date)) / 86_400_000);
}
