/** Whole cents ⇄ decimal strings for the packages screens (U-02): amounts are never floats. */
import { formatMoney, parseMoney, type AppLocale } from "@numo9/ui";

export function centsToDecimal(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(Math.trunc(cents));
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}`;
}

/** `$49.00` / `49,00 $` from whole cents. */
export function money(cents: number, locale: AppLocale): string {
  return formatMoney(centsToDecimal(cents), { locale });
}

/** Whole cents from what a person typed (`49`, `$1,234.50`, `49,00 $`), or null if unreadable. */
export function parseCents(text: string, locale: AppLocale): number | null {
  const parsed = parseMoney(text, { locale, fractionDigits: 2 });
  if (parsed === null || parsed.startsWith("-")) return null;
  const [whole, fraction = ""] = parsed.split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0").slice(0, 2));
}
