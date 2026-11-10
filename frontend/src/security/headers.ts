/**
 * Security response headers for every route of the web app (S-03-T10).
 *
 * Pages also get their nonce-based Content-Security-Policy from the middleware (S-03-T02);
 * route handlers under /api/ return data, never markup, so they get `default-src 'none'`.
 * `tools/ci/check_security_headers.py` grades the running app in CI (securityheaders-style);
 * the backend sends the same set (`backend/numo9/security/headers.py`).
 */
export interface HeaderPair {
  key: string;
  value: string;
}

/** Every powerful browser feature off; `payment` only for Stripe Elements (U-04). */
export const PERMISSIONS_POLICY = [
  "accelerometer=()",
  "camera=()",
  "display-capture=()",
  "geolocation=()",
  "gyroscope=()",
  "magnetometer=()",
  "microphone=()",
  'payment=(self "https://js.stripe.com")',
  "usb=()",
].join(", ");

export const HSTS = "max-age=31536000; includeSubDomains; preload";

export const API_CSP =
  "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'";

/** Headers sent on every response. HSTS only from production builds (served behind TLS). */
export function securityHeaders({ production }: { production: boolean }): HeaderPair[] {
  return [
    { key: "X-Frame-Options", value: "DENY" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: PERMISSIONS_POLICY },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
    ...(production ? [{ key: "Strict-Transport-Security", value: HSTS }] : []),
  ];
}

/** `next.config.ts` `headers()` entries. */
export function headerRules(production: boolean) {
  return [
    { source: "/:path*", headers: securityHeaders({ production }) },
    { source: "/api/:path*", headers: [{ key: "Content-Security-Policy", value: API_CSP }] },
  ];
}
