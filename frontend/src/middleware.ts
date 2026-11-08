import { NextResponse, type NextRequest } from "next/server";

import { resolveRedirect } from "@/routing/redirects";
import { CURRENT_ORG_COOKIE } from "@/routing/routes";

/** Redirect map (S-01-T14): root, `/o/:org` and legacy-style URLs land on the right module. */
export function middleware(request: NextRequest): NextResponse {
  const redirect = resolveRedirect(request.nextUrl.pathname, {
    currentOrg: request.cookies.get(CURRENT_ORG_COOKIE)?.value,
  });
  if (redirect === null) return NextResponse.next();

  const url = request.nextUrl.clone(); // keeps the query string
  url.pathname = redirect.location;
  return NextResponse.redirect(url, redirect.status);
}

export const config = {
  // Pages only: skip Next.js internals, API routes and well-known static files.
  matcher: ["/((?!_next/|api/|favicon\\.ico$|robots\\.txt$|sitemap\\.xml$).*)"],
};
