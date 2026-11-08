/**
 * Redirect map (S-01-T14, gap #2). Pure function used by `src/middleware.ts`.
 *
 *   resolveRedirect("/o/acme")                → 301 /o/acme/home
 *   resolveRedirect("/O/Acme/Settings/")      → 301 /o/acme/settings/general
 *   resolveRedirect("/dashboard", { org })    → 307 /o/<org>/home   (no org → 307 /)
 *   resolveRedirect("/dashbaord")             → 307 like "/dashboard" (typo, edit distance 1)
 *   resolveRedirect("/no-such-page")          → null → custom 404 with search
 *
 * Status codes: 301 when the target depends only on the URL (safe for browsers to cache);
 * 307 when it depends on the current-organisation cookie or on typo correction, which must not
 * be cached permanently. The root `/` is Home itself and never redirects.
 *
 * Locations are built only from registry paths and a validated slug — never from the request —
 * so the map cannot be used as an open redirect.
 */
import { findOrgModule, ORG_MODULES, ORG_SLUG, orgModuleUrl } from "./routes";

export interface RedirectContext {
  /** Raw value of the current-organisation cookie, if present (validated here). */
  currentOrg?: string | null;
}

export interface Redirect {
  location: string;
  status: 301 | 307;
}

/** alias (lowercase, no leading slash) → canonical module path. Canonical paths map to themselves. */
const ALIASES: ReadonlyMap<string, string> = new Map(
  ORG_MODULES.flatMap((module) => [
    [module.path, module.path] as const,
    ...module.aliases.map((alias) => [alias, module.path] as const),
  ]),
);

/** Single-word keys eligible for typo correction (no "/" or "."). */
const TYPO_CANDIDATES: readonly string[] = [...ALIASES.keys()].filter((key) =>
  /^[a-z-]+$/.test(key),
);

function normalise(pathname: string): string {
  let path = pathname.toLowerCase().replace(/\/{2,}/g, "/");
  if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
  return path;
}

/** Optimal-string-alignment distance (Levenshtein + adjacent transposition). */
export function editDistance(a: string, b: string): number {
  const rows = a.length + 1;
  const cols = b.length + 1;
  const d: number[][] = Array.from({ length: rows }, (_, i) =>
    Array.from({ length: cols }, (_, j) => (i === 0 ? j : j === 0 ? i : 0)),
  );
  const at = (i: number, j: number): number => d[i]?.[j] ?? Number.POSITIVE_INFINITY;
  for (let i = 1; i < rows; i++) {
    for (let j = 1; j < cols; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      let value = Math.min(at(i - 1, j) + 1, at(i, j - 1) + 1, at(i - 1, j - 1) + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        value = Math.min(value, at(i - 2, j - 2) + 1);
      }
      d[i]![j] = value;
    }
  }
  return at(a.length, b.length);
}

/** Unique closest alias for a single mistyped word, or undefined when unsure. */
export function correctTypo(word: string): string | undefined {
  if (!/^[a-z-]{4,40}$/.test(word)) return undefined;
  const maxDistance = word.length >= 8 ? 2 : 1;
  let best: string | undefined;
  let bestDistance = Number.POSITIVE_INFINITY;
  let tie = false;
  for (const candidate of TYPO_CANDIDATES) {
    const distance = editDistance(word, candidate);
    if (distance < bestDistance) {
      best = candidate;
      bestDistance = distance;
      tie = false;
    } else if (distance === bestDistance && ALIASES.get(candidate) !== ALIASES.get(best ?? "")) {
      tie = true; // two different modules equally close: do not guess
    }
  }
  if (best === undefined || tie || bestDistance === 0 || bestDistance > maxDistance)
    return undefined;
  return best;
}

function validOrg(value: string | null | undefined): string | undefined {
  const org = value?.toLowerCase();
  return org !== undefined && ORG_SLUG.test(org) ? org : undefined;
}

export function resolveRedirect(pathname: string, context: RedirectContext = {}): Redirect | null {
  if (pathname === "/") return null;
  const path = normalise(pathname);

  // ---- organisation-scoped: /o/:org[/...] -----------------------------------------------
  const scoped = /^\/o\/([^/]+)(?:\/(.*))?$/.exec(path);
  if (scoped) {
    const org = validOrg(scoped[1]);
    if (org === undefined) return null; // invalid slug → 404
    const rest = scoped[2] ?? "";
    if (rest === "") return { location: orgModuleUrl(org, "home"), status: 301 };

    if (findOrgModule(rest)) {
      const canonical = orgModuleUrl(org, rest);
      return canonical === pathname ? null : { location: canonical, status: 301 };
    }
    const target = ALIASES.get(rest);
    if (target !== undefined) return { location: orgModuleUrl(org, target), status: 301 };

    const typo = correctTypo(rest);
    const typoTarget = typo === undefined ? undefined : ALIASES.get(typo);
    if (typoTarget !== undefined) return { location: orgModuleUrl(org, typoTarget), status: 307 };
    return null;
  }

  // ---- legacy-style path without an organisation ---------------------------------------
  const key = path.slice(1);
  let target = ALIASES.get(key);
  if (target === undefined) {
    const typo = correctTypo(key);
    target = typo === undefined ? undefined : ALIASES.get(typo);
  }
  if (target === undefined) return null;

  const org = validOrg(context.currentOrg);
  return { location: org === undefined ? "/" : orgModuleUrl(org, target), status: 307 };
}
