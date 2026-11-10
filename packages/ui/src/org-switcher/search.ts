/**
 * Organisation search for the org switcher (A-01-T14): case- and accent-insensitive, every word of
 * the query must appear in the name ("maple sup" finds "Maple Leaf Supply Ltd.", "quebec" finds
 * "Québec"). Pure functions so the switcher stays fast with 2,000 organisations.
 */

/** Lower-case and strip diacritics: "Érable Québec" → "erable quebec". */
export function normaliseForSearch(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLocaleLowerCase("en-CA")
    .trim();
}

/** Query words (normalised, empty words dropped). */
export function queryWords(query: string): string[] {
  return normaliseForSearch(query).split(/\s+/).filter(Boolean);
}

export interface SearchableOrg {
  id: string;
  name: string;
}

/**
 * Organisations whose name contains every query word, names starting with the first word first,
 * then alphabetical. An empty query returns an empty list (the switcher shows recent ones instead).
 */
export function searchOrganisations<T extends SearchableOrg>(
  organisations: readonly T[],
  query: string,
): T[] {
  const words = queryWords(query);
  if (words.length === 0) return [];
  const first = words[0] ?? "";
  const scored: { org: T; name: string; starts: boolean }[] = [];
  for (const org of organisations) {
    const name = normaliseForSearch(org.name);
    if (words.every((word) => name.includes(word))) {
      scored.push({ org, name, starts: name.startsWith(first) });
    }
  }
  scored.sort((a, b) => {
    if (a.starts !== b.starts) return a.starts ? -1 : 1;
    return a.name.localeCompare(b.name, "en-CA");
  });
  return scored.map((entry) => entry.org);
}

/**
 * The recent organisations to list: ids in `recentIds` order (most recent first) that are still
 * accessible, at most `limit`. Ids the user can no longer access are skipped.
 */
export function recentOrganisations<T extends SearchableOrg>(
  organisations: readonly T[],
  recentIds: readonly string[],
  limit = 5,
): T[] {
  const byId = new Map(organisations.map((org) => [org.id, org]));
  const picked: T[] = [];
  for (const id of recentIds) {
    const org = byId.get(id);
    if (org && !picked.includes(org)) picked.push(org);
    if (picked.length === limit) break;
  }
  return picked;
}
