/**
 * Recent organisations for the org switcher (A-01-T14): the last 5 organisations the user opened,
 * most recent first, kept in this browser (localStorage). Storage may be unavailable (private
 * window, blocked site data): reads then return an empty list and writes are skipped.
 *
 * Opening an organisation also writes the current-organisation cookie that the redirect map
 * (S-01-T14) uses to send `/` and legacy URLs to the right organisation.
 */
import { CURRENT_ORG_COOKIE, ORG_SLUG } from "@/routing/routes";

export const RECENT_ORGS_KEY = "numo9.recentOrgs";
export const RECENT_ORGS_LIMIT = 5;

export function readRecentOrgs(storage: Storage | undefined = safeLocalStorage()): string[] {
  try {
    const raw = storage?.getItem(RECENT_ORGS_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((id): id is string => typeof id === "string" && ORG_SLUG.test(id))
      .slice(0, RECENT_ORGS_LIMIT);
  } catch {
    return [];
  }
}

/** Move `org` to the front of the recent list (max 5) and return the new list. */
export function rememberOrg(
  org: string,
  storage: Storage | undefined = safeLocalStorage(),
): string[] {
  if (!ORG_SLUG.test(org)) return readRecentOrgs(storage);
  const next = [org, ...readRecentOrgs(storage).filter((id) => id !== org)].slice(
    0,
    RECENT_ORGS_LIMIT,
  );
  try {
    storage?.setItem(RECENT_ORGS_KEY, JSON.stringify(next));
  } catch {
    // Storage full or blocked: the list simply isn't kept.
  }
  return next;
}

/** Remember the current organisation for the redirect map (1 year, whole site, Lax). */
export function writeCurrentOrgCookie(org: string, doc: Document | undefined = globalDocument()) {
  if (!doc || !ORG_SLUG.test(org)) return;
  const secure = doc.location?.protocol === "https:" ? "; Secure" : "";
  doc.cookie = `${CURRENT_ORG_COOKIE}=${org}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
}

function safeLocalStorage(): Storage | undefined {
  try {
    return typeof window === "undefined" ? undefined : window.localStorage;
  } catch {
    return undefined;
  }
}

function globalDocument(): Document | undefined {
  return typeof document === "undefined" ? undefined : document;
}
