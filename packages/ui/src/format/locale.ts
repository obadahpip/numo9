/**
 * Locales of the formatters (A-10-T08): English (Canada), French (Canada) and the pseudo-locale
 * `en-XA` (A-10-T13), which formats like en-CA.
 */
export type AppLocale = "en-CA" | "fr-CA" | "en-XA";

export type TimeFormat = "12h" | "24h";

/** Locale used for `Intl` data (the pseudo-locale formats like English). */
export function intlLocale(locale: AppLocale): "en-CA" | "fr-CA" {
  return locale === "fr-CA" ? "fr-CA" : "en-CA";
}

/** Default time display per locale: 12 h in English, 24 h in French (as the backend user default). */
export function defaultTimeFormat(locale: AppLocale): TimeFormat {
  return locale === "fr-CA" ? "24h" : "12h";
}

/** Default organisation time zone (Phase 0: America/Toronto). */
export const DEFAULT_TIME_ZONE = "America/Toronto";
