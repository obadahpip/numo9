/**
 * Backend proxy for local development (A-02-T10): the web app calls the API on its own origin —
 * `/api/v1/…` (Numo9 API) and `/_allauth/…` (authentication) — so session and CSRF cookies stay
 * first-party. In staging/production the reverse proxy (Caddy, S-02) routes those paths to the
 * backend; locally `NUMO9_BACKEND_URL` (e.g. `http://backend:8000` in docker-compose.dev.yml)
 * makes Next.js forward them. Unset → no rewrites (tests answer the API with fixtures).
 *
 * Next.js route handlers such as `/api/csp-report` are matched before these rewrites.
 */
export interface Rewrite {
  source: string;
  destination: string;
}

export const BACKEND_PATHS = ["/api/v1/:path*", "/_allauth/:path*"] as const;

export function backendRewrites(backendUrl: string | undefined): Rewrite[] {
  const base = backendUrl?.trim().replace(/\/+$/, "");
  if (!base) return [];
  let url: URL;
  try {
    url = new URL(base);
  } catch {
    throw new Error(
      `NUMO9_BACKEND_URL must be an absolute http(s) URL, got ${JSON.stringify(backendUrl)}`,
    );
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`NUMO9_BACKEND_URL must use http or https, got ${url.protocol}`);
  }
  return BACKEND_PATHS.map((source) => ({ source, destination: `${base}${source}` }));
}
