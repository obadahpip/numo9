/**
 * Locales of the web app (A-10-T13): English (Canada) is the source and default, French (Canada)
 * ships keys from day one (text in Phase 6), and the pseudo-locale `en-XA` (accented, +30 %
 * length) is for layout testing outside production.
 */
export const LOCALES = ["en-CA", "fr-CA"] as const;
export type Locale = (typeof LOCALES)[number];
export const PSEUDO_LOCALE = "en-XA";
export type AppLocale = Locale | typeof PSEUDO_LOCALE;

export const DEFAULT_LOCALE: Locale = "en-CA";
/** Cookie holding the chosen locale (A-02 writes it from the user's `locale` preference). */
export const LOCALE_COOKIE = "numo9_locale";

/** True when the pseudo-locale may be chosen: never in production unless explicitly enabled. */
export function pseudoLocaleEnabled(
  env: Record<string, string | undefined> = process.env,
): boolean {
  if (env.NUMO9_PSEUDO_LOCALE !== undefined) return env.NUMO9_PSEUDO_LOCALE === "1";
  return env.NODE_ENV !== "production";
}

function normalise(tag: string): string {
  const [lang = "", region = ""] = tag.trim().replace("_", "-").split("-");
  return region ? `${lang.toLowerCase()}-${region.toUpperCase()}` : lang.toLowerCase();
}

/**
 * The locale for a request: the cookie if valid, else the best match from Accept-Language
 * (`fr`, `fr-FR`, `fr-CA` → fr-CA; anything else → en-CA).
 */
export function resolveLocale({
  cookie,
  acceptLanguage,
  pseudo = false,
}: {
  cookie?: string | null;
  acceptLanguage?: string | null;
  pseudo?: boolean;
}): AppLocale {
  if (cookie) {
    const tag = normalise(cookie);
    if ((LOCALES as readonly string[]).includes(tag)) return tag as Locale;
    if (pseudo && tag === PSEUDO_LOCALE) return PSEUDO_LOCALE;
  }
  const ranked = (acceptLanguage ?? "")
    .split(",")
    .map((part) => {
      const [tag = "", q] = part.trim().split(";q=");
      return { tag: normalise(tag), q: q === undefined ? 1 : Number(q) };
    })
    .filter((entry) => entry.tag && entry.q > 0)
    .sort((a, b) => b.q - a.q);
  for (const { tag } of ranked) {
    if ((LOCALES as readonly string[]).includes(tag)) return tag as Locale;
    const language = tag.split("-")[0];
    if (language === "fr") return "fr-CA";
    if (language === "en") return "en-CA";
  }
  return DEFAULT_LOCALE;
}
