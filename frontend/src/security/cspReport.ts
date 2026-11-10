/**
 * Parsing of CSP violation reports (S-03-T02) for `app/api/csp-report/route.ts`: `report-uri`
 * bodies (`application/csp-report`) and Reporting API batches (`application/reports+json`).
 * URLs keep origin and path only — query strings and fragments can carry tokens or personal data.
 */
export interface CspViolation {
  documentUri: string;
  blockedUri: string;
  effectiveDirective: string;
  disposition: string;
  sourceFile: string;
  lineNumber: number | null;
}

export function stripUrl(value: unknown): string {
  if (typeof value !== "string") return "";
  if (!/^[a-z][a-z0-9+.-]*:/i.test(value)) return value.slice(0, 64); // "inline", "eval", …
  try {
    const url = new URL(value);
    return `${url.origin}${url.pathname}`.slice(0, 512);
  } catch {
    return "";
  }
}

function field(body: Record<string, unknown>, ...names: string[]): unknown {
  for (const name of names) if (body[name] !== undefined) return body[name];
  return undefined;
}

export function normaliseReport(body: Record<string, unknown>): CspViolation {
  const line = field(body, "line-number", "lineNumber");
  const directive = field(body, "effective-directive", "effectiveDirective", "violated-directive");
  return {
    documentUri: stripUrl(field(body, "document-uri", "documentURL")),
    blockedUri: stripUrl(field(body, "blocked-uri", "blockedURL")),
    effectiveDirective: typeof directive === "string" ? directive.split(" ")[0]!.slice(0, 64) : "",
    disposition: String(field(body, "disposition") ?? "enforce").slice(0, 16),
    sourceFile: stripUrl(field(body, "source-file", "sourceFile")),
    lineNumber: typeof line === "number" ? line : null,
  };
}

export function parseReports(contentType: string, text: string): CspViolation[] | null {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return null;
  }
  if (contentType.includes("application/reports+json")) {
    if (!Array.isArray(data)) return null;
    return data
      .filter((r) => r && r.type === "csp-violation" && typeof r.body === "object" && r.body)
      .map((r) => normaliseReport(r.body as Record<string, unknown>));
  }
  const report = (data as { "csp-report"?: unknown })?.["csp-report"];
  if (!report || typeof report !== "object") return null;
  return [normaliseReport(report as Record<string, unknown>)];
}
