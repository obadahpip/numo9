/** Message catalogues per locale (A-10-T13). en-XA is generated from en-CA at load time. */
import type { AppLocale } from "./locales";
import { pseudoCatalog, type Catalog } from "./pseudo";

export async function loadMessages(locale: AppLocale): Promise<Catalog> {
  switch (locale) {
    case "fr-CA":
      return (await import("../../messages/fr-CA.json")).default as Catalog;
    case "en-XA":
      return pseudoCatalog((await import("../../messages/en-CA.json")).default as Catalog);
    default:
      return (await import("../../messages/en-CA.json")).default as Catalog;
  }
}
