/**
 * Content Security Policy with per-request nonces (S-03-T02).
 *
 * The middleware creates a fresh nonce for every page request and sends this policy; Next.js
 * reads the nonce from the request's CSP header and puts it on its own inline scripts. The only
 * third party allowed is Stripe (Elements / Checkout, U-04); everything else is same-origin.
 * Violations are reported to `/api/csp-report` (`report-uri`).
 *
 * Stripe's required sources: https://docs.stripe.com/security/guide#content-security-policy
 */
export const STRIPE_SOURCES = {
  script: ["https://js.stripe.com", "https://*.js.stripe.com"],
  frame: ["https://js.stripe.com", "https://*.js.stripe.com", "https://hooks.stripe.com"],
  connect: ["https://api.stripe.com"],
  img: ["https://*.stripe.com"],
} as const;

export const CSP_REPORT_PATH = "/api/csp-report";

export type CspMode = "enforce" | "report-only";

export interface CspOptions {
  nonce: string;
  /** `next dev` needs 'unsafe-eval' (React Refresh); never in a production build. */
  dev?: boolean;
  /** Extra origins the app calls, e.g. the API origin `https://api.numo9.ca`. */
  connectSrc?: readonly string[];
}

/** 128 random bits, base64 — a new value for every response. */
export function generateNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

export function cspDirectives({ nonce, dev = false, connectSrc = [] }: CspOptions) {
  const n = `'nonce-${nonce}'`;
  return {
    "default-src": ["'self'"],
    "script-src": ["'self'", n, ...STRIPE_SOURCES.script, ...(dev ? ["'unsafe-eval'"] : [])],
    "style-src": ["'self'", n],
    // React renders `style` attributes (virtualised grids, positioning); no inline <style>.
    "style-src-attr": ["'unsafe-inline'"],
    "img-src": ["'self'", "data:", "blob:", ...STRIPE_SOURCES.img],
    "font-src": ["'self'", "data:"],
    "connect-src": ["'self'", ...STRIPE_SOURCES.connect, ...connectSrc, ...(dev ? ["ws:"] : [])],
    "frame-src": [...STRIPE_SOURCES.frame],
    "worker-src": ["'self'", "blob:"],
    "manifest-src": ["'self'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
    // report-uri only: browsers send it at once. (With `report-to` as well, Chrome switches to
    // the Reporting API, which batches reports for up to a minute.) The endpoint also accepts
    // Reporting API bodies for when report-to is added.
    "report-uri": [CSP_REPORT_PATH],
  } satisfies Record<string, readonly string[]>;
}

export function buildCsp(options: CspOptions): string {
  return Object.entries(cspDirectives(options))
    .map(([name, values]) => `${name} ${values.join(" ")}`)
    .join("; ");
}

/** `NUMO9_CSP_MODE=report-only` for the first week on a new environment (plan risk), else enforce. */
export function cspMode(value: string | undefined): CspMode {
  return value?.trim().toLowerCase() === "report-only" ? "report-only" : "enforce";
}

export function cspHeaderName(mode: CspMode): string {
  return mode === "report-only" ? "Content-Security-Policy-Report-Only" : "Content-Security-Policy";
}

/** Origins from `NUMO9_CSP_CONNECT_SRC` (comma-separated); only `https://` origins are kept. */
export function connectSources(value: string | undefined): string[] {
  return (value ?? "")
    .split(",")
    .map((origin) => origin.trim())
    .filter((origin) => /^https:\/\/[a-z0-9.-]+(:\d+)?$/i.test(origin));
}
