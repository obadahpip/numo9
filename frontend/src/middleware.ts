import { NextResponse, type NextRequest } from "next/server";

import { resolveRedirect } from "@/routing/redirects";
import { CURRENT_ORG_COOKIE } from "@/routing/routes";
import { buildCsp, connectSources, cspHeaderName, cspMode, generateNonce } from "@/security/csp";

/**
 * Every page request:
 * 1. redirect map (S-01-T14): root, `/o/:org` and legacy-style URLs land on the right module;
 * 2. Content Security Policy with a fresh nonce (S-03-T02). The nonce goes to Next.js in the
 *    request's CSP header (it adds it to its inline scripts) and to the browser in the response.
 */
export function middleware(request: NextRequest): NextResponse {
  const redirect = resolveRedirect(request.nextUrl.pathname, {
    currentOrg: request.cookies.get(CURRENT_ORG_COOKIE)?.value,
  });
  if (redirect !== null) {
    const url = request.nextUrl.clone(); // keeps the query string
    url.pathname = redirect.location;
    return NextResponse.redirect(url, redirect.status);
  }

  const nonce = generateNonce();
  const policy = buildCsp({
    nonce,
    dev: process.env.NODE_ENV === "development",
    connectSrc: connectSources(process.env.NUMO9_CSP_CONNECT_SRC),
    storageSrc: connectSources(process.env.NUMO9_CSP_STORAGE_SRC),
  });
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", policy);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set(cspHeaderName(cspMode(process.env.NUMO9_CSP_MODE)), policy);
  return response;
}

export const config = {
  // Pages only: skip Next.js internals, API routes and well-known static files.
  matcher: ["/((?!_next/|api/|favicon\\.ico$|robots\\.txt$|sitemap\\.xml$).*)"],
};
