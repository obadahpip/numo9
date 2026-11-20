/**
 * Recent palette picks (A-09-T07): the last 5 things opened from the command palette in an
 * organisation, most recent first, kept in this browser (localStorage, per organisation). Storage
 * may be unavailable: reads then return nothing and writes are skipped.
 */
export const RECENTS_LIMIT = 5;

export interface RecentPick {
  /** Unique within the palette: `records:<id>`, `settings:<key>`, `create:<id>`… */
  id: string;
  title: string;
  url: string;
}

const key = (org: string) => `numo9.palette.recent.${org}`;

function storage(): Storage | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.localStorage;
  } catch {
    return undefined;
  }
}

function isPick(value: unknown): value is RecentPick {
  const v = value as Partial<RecentPick> | null;
  return (
    !!v &&
    typeof v.id === "string" &&
    typeof v.title === "string" &&
    typeof v.url === "string" &&
    v.url.startsWith("/")
  );
}

export function readRecents(org: string, store: Storage | undefined = storage()): RecentPick[] {
  try {
    const raw = store?.getItem(key(org));
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter(isPick).slice(0, RECENTS_LIMIT) : [];
  } catch {
    return [];
  }
}

export function rememberPick(
  org: string,
  pick: RecentPick,
  store: Storage | undefined = storage(),
): RecentPick[] {
  const next = [pick, ...readRecents(org, store).filter((p) => p.id !== pick.id)].slice(
    0,
    RECENTS_LIMIT,
  );
  try {
    store?.setItem(key(org), JSON.stringify(next));
  } catch {
    // Storage full or blocked: the list simply isn't kept.
  }
  return next;
}
