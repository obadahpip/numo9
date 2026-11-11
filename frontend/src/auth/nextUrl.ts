/**
 * Where to go after signing in (A-02-T11): the `next` query parameter when it is a same-site
 * path (`/o/acme/contacts`), otherwise Home. Absolute URLs, protocol-relative `//host`, back
 * slashes and control characters are refused, so the login page cannot be used as an open
 * redirect.
 */
export function safeNextUrl(next: string | null | undefined): string {
  if (!next || next.length > 2048) return "/";
  if (!next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/";
  if (/[\u0000-\u001f\\]/.test(next)) return "/";
  // Never back to an auth screen (a loop after signing in).
  if (/^\/(login|signup|2fa|reset|verify)(\/|$|\?)/.test(next)) return "/";
  return next;
}
