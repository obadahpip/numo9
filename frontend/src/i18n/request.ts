/**
 * next-intl request configuration (A-10-T13): locale from the `numo9_locale` cookie or the
 * browser's Accept-Language; ICU catalogues from `frontend/messages/<locale>.json`. No locale in
 * the URL: `/o/:org/…` stays the same in every language.
 */
import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";

import { LOCALE_COOKIE, pseudoLocaleEnabled, resolveLocale } from "./locales";
import { loadMessages } from "./messages";

export default getRequestConfig(async () => {
  const [cookieStore, headerList] = await Promise.all([cookies(), headers()]);
  const locale = resolveLocale({
    cookie: cookieStore.get(LOCALE_COOKIE)?.value,
    acceptLanguage: headerList.get("accept-language"),
    pseudo: pseudoLocaleEnabled(),
  });
  return {
    locale,
    messages: await loadMessages(locale),
    timeZone: "America/Toronto",
  };
});
