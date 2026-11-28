/** Tabs of the Assurance page (K-09-T23/T24), also read by the server page from `?tab=`. */
export const ASSURANCE_TABS = ["findings", "rules", "activity"] as const;
export type AssuranceTab = (typeof ASSURANCE_TABS)[number];

export const isAssuranceTab = (value: unknown): value is AssuranceTab =>
  typeof value === "string" && (ASSURANCE_TABS as readonly string[]).includes(value);
