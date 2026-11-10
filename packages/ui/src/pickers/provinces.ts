/**
 * Canadian provinces and territories (ISO 3166-2:CA codes), English and French names as used by
 * the CRA and Revenu Québec. Reference data, not UI text: the picker shows the name for the
 * user's locale.
 */
export interface Province {
  code: string;
  en: string;
  fr: string;
  kind: "province" | "territory";
  /** First letters a postal code in this province can start with. */
  postalPrefixes: string;
}

export const PROVINCES: readonly Province[] = [
  { code: "AB", en: "Alberta", fr: "Alberta", kind: "province", postalPrefixes: "T" },
  {
    code: "BC",
    en: "British Columbia",
    fr: "Colombie-Britannique",
    kind: "province",
    postalPrefixes: "V",
  },
  { code: "MB", en: "Manitoba", fr: "Manitoba", kind: "province", postalPrefixes: "R" },
  {
    code: "NB",
    en: "New Brunswick",
    fr: "Nouveau-Brunswick",
    kind: "province",
    postalPrefixes: "E",
  },
  {
    code: "NL",
    en: "Newfoundland and Labrador",
    fr: "Terre-Neuve-et-Labrador",
    kind: "province",
    postalPrefixes: "A",
  },
  { code: "NS", en: "Nova Scotia", fr: "Nouvelle-Écosse", kind: "province", postalPrefixes: "B" },
  { code: "ON", en: "Ontario", fr: "Ontario", kind: "province", postalPrefixes: "KLMNP" },
  {
    code: "PE",
    en: "Prince Edward Island",
    fr: "Île-du-Prince-Édouard",
    kind: "province",
    postalPrefixes: "C",
  },
  { code: "QC", en: "Quebec", fr: "Québec", kind: "province", postalPrefixes: "GHJ" },
  { code: "SK", en: "Saskatchewan", fr: "Saskatchewan", kind: "province", postalPrefixes: "S" },
  {
    code: "NT",
    en: "Northwest Territories",
    fr: "Territoires du Nord-Ouest",
    kind: "territory",
    postalPrefixes: "X",
  },
  { code: "NU", en: "Nunavut", fr: "Nunavut", kind: "territory", postalPrefixes: "X" },
  { code: "YT", en: "Yukon", fr: "Yukon", kind: "territory", postalPrefixes: "Y" },
];

export function provinceName(code: string, locale: string): string | undefined {
  const province = PROVINCES.find((p) => p.code === code);
  if (!province) return undefined;
  return locale === "fr-CA" ? province.fr : province.en;
}
