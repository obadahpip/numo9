import { formatMoney } from "@numo9/ui";

import type { AppLocale } from "@/i18n/locales";

/** Cents from the billing API as money: `$49.00` / `49,00 $`. */
export function money(cents: number | null | undefined, locale: AppLocale): string {
  return formatMoney(((cents ?? 0) / 100).toFixed(2), { locale });
}
