import { NextResponse } from "next/server";

import { parseReports } from "@/security/cspReport";

/**
 * CSP violation reports (S-03-T02): `report-uri` (`application/csp-report`) and the Reporting
 * API (`application/reports+json`). Each report is logged as one JSON line (`csp.violation`) for
 * the log pipeline; URLs lose their query string and fragment (they can carry tokens or
 * personal data). Bodies over 16 KB are refused; at most 120 reports per minute per process are
 * logged.
 */
const MAX_BYTES = 16 * 1024;
const PER_MINUTE = 120;

let windowStart = 0;
let logged = 0;

export async function POST(request: Request): Promise<Response> {
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (declared > MAX_BYTES) return new NextResponse(null, { status: 413 });
  const text = await request.text();
  if (text.length > MAX_BYTES) return new NextResponse(null, { status: 413 });

  const reports = parseReports(request.headers.get("content-type") ?? "", text);
  if (reports === null) return new NextResponse(null, { status: 400 });

  const now = Date.now();
  if (now - windowStart > 60_000) {
    windowStart = now;
    logged = 0;
  }
  for (const report of reports) {
    if (logged >= PER_MINUTE) break;
    logged += 1;
    console.warn(JSON.stringify({ event: "csp.violation", ...report }));
  }
  return new NextResponse(null, { status: 204 });
}
