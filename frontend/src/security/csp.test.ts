// @vitest-environment node
import { NextRequest } from "next/server";

import { middleware } from "@/middleware";

import {
  buildCsp,
  connectSources,
  cspDirectives,
  cspHeaderName,
  cspMode,
  generateNonce,
  STRIPE_SOURCES,
} from "./csp";
import { normaliseReport, parseReports, stripUrl } from "./cspReport";

/** S-03-T02 — CSP with nonces; Stripe is the only third party; report parsing. */
describe("Content Security Policy (S-03-T02)", () => {
  it("creates a fresh 128-bit base64 nonce each time", () => {
    const nonces = new Set(Array.from({ length: 50 }, generateNonce));
    expect(nonces.size).toBe(50);
    for (const nonce of nonces) expect(atob(nonce)).toHaveLength(16);
  });

  it("allows scripts from self, the nonce and Stripe only — no unsafe-inline/eval", () => {
    const directives = cspDirectives({ nonce: "abc" });
    expect(directives["script-src"]).toEqual([
      "'self'",
      "'nonce-abc'",
      "https://js.stripe.com",
      "https://*.js.stripe.com",
    ]);
    const policy = buildCsp({ nonce: "abc" });
    expect(policy).not.toMatch(/script-src[^;]*unsafe/);
    expect(policy).toContain("object-src 'none'");
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).toContain("base-uri 'self'");
    expect(policy).toContain("report-uri /api/csp-report");
  });

  it("names no third-party host other than Stripe", () => {
    const hosts = buildCsp({ nonce: "n" })
      .split(/[;\s]+/)
      .filter((token) => token.startsWith("https://"));
    expect(hosts.length).toBeGreaterThan(0);
    for (const host of hosts) expect(host).toMatch(/^https:\/\/([*a-z0-9-]+\.)*stripe\.com$/);
    expect(STRIPE_SOURCES.frame).toContain("https://hooks.stripe.com");
  });

  it("adds 'unsafe-eval' and websockets only for next dev", () => {
    expect(buildCsp({ nonce: "n", dev: true })).toMatch(/script-src[^;]*'unsafe-eval'/);
    expect(buildCsp({ nonce: "n", dev: true })).toMatch(/connect-src[^;]* ws:/);
  });

  it("adds configured https API origins to connect-src and drops anything else", () => {
    expect(
      connectSources("https://api.numo9.ca, http://evil.test, javascript:x,https://a.b:8443"),
    ).toEqual(["https://api.numo9.ca", "https://a.b:8443"]);
    expect(buildCsp({ nonce: "n", connectSrc: ["https://api.numo9.ca"] })).toContain(
      "connect-src 'self' https://api.stripe.com https://api.numo9.ca",
    );
  });

  it("allows the files bucket for uploads (connect-src) and previews (img-src)", () => {
    const csp = buildCsp({ nonce: "n", storageSrc: ["https://files.numo9.ca"] });
    expect(csp).toContain(
      "img-src 'self' data: blob: https://*.stripe.com https://files.numo9.ca;",
    );
    expect(csp).toContain("connect-src 'self' https://api.stripe.com https://files.numo9.ca");
  });

  it("switches to report-only only when asked", () => {
    expect(cspMode(undefined)).toBe("enforce");
    expect(cspMode("Report-Only")).toBe("report-only");
    expect(cspHeaderName("report-only")).toBe("Content-Security-Policy-Report-Only");
    expect(cspHeaderName("enforce")).toBe("Content-Security-Policy");
  });
});

describe("middleware CSP header", () => {
  it("sends a policy whose nonce matches the one given to Next.js, new per request", () => {
    const first = middleware(new NextRequest("http://localhost/o/acme/home"));
    const second = middleware(new NextRequest("http://localhost/o/acme/home"));
    const policy = first.headers.get("content-security-policy")!;
    const nonce = /'nonce-([^']+)'/.exec(policy)![1]!;
    // NextResponse.next({ request: { headers } }) forwards overridden request headers.
    expect(first.headers.get("x-middleware-request-x-nonce")).toBe(nonce);
    expect(first.headers.get("x-middleware-request-content-security-policy")).toBe(policy);
    expect(second.headers.get("content-security-policy")).not.toBe(policy);
  });

  it("uses the report-only header when NUMO9_CSP_MODE=report-only", () => {
    vi.stubEnv("NUMO9_CSP_MODE", "report-only");
    const response = middleware(new NextRequest("http://localhost/o/acme/home"));
    expect(response.headers.get("content-security-policy")).toBeNull();
    expect(response.headers.get("content-security-policy-report-only")).toContain("'nonce-");
    vi.unstubAllEnvs();
  });

  it("does not add a policy to redirects", () => {
    const response = middleware(new NextRequest("http://localhost/HOME"));
    expect(response.status).toBeGreaterThanOrEqual(300);
    expect(response.headers.get("content-security-policy")).toBeNull();
  });
});

describe("CSP violation reports", () => {
  it("parses report-uri bodies and strips query strings", () => {
    const reports = parseReports(
      "application/csp-report",
      JSON.stringify({
        "csp-report": {
          "document-uri": "https://app.numo9.ca/o/acme/home?token=secret#x",
          "blocked-uri": "https://cdn.example.com/x.js?id=9",
          "violated-directive": "script-src-elem",
          "effective-directive": "script-src-elem",
          "source-file": "https://app.numo9.ca/_next/static/chunks/a.js",
          "line-number": 3,
        },
      }),
    );
    expect(reports).toEqual([
      {
        documentUri: "https://app.numo9.ca/o/acme/home",
        blockedUri: "https://cdn.example.com/x.js",
        effectiveDirective: "script-src-elem",
        disposition: "enforce",
        sourceFile: "https://app.numo9.ca/_next/static/chunks/a.js",
        lineNumber: 3,
      },
    ]);
  });

  it("parses Reporting API batches and ignores other report types", () => {
    const reports = parseReports(
      "application/reports+json",
      JSON.stringify([
        {
          type: "csp-violation",
          body: {
            documentURL: "https://app.numo9.ca/",
            blockedURL: "inline",
            effectiveDirective: "style-src-elem",
            disposition: "report",
          },
        },
        { type: "deprecation", body: {} },
      ]),
    );
    expect(reports).toHaveLength(1);
    expect(reports![0]).toMatchObject({ blockedUri: "inline", disposition: "report" });
  });

  it("rejects malformed bodies", () => {
    expect(parseReports("application/csp-report", "{")).toBeNull();
    expect(parseReports("application/csp-report", "{}")).toBeNull();
    expect(parseReports("application/reports+json", "{}")).toBeNull();
  });

  it("keeps URL fields short and safe", () => {
    expect(stripUrl("eval")).toBe("eval");
    expect(stripUrl(42)).toBe("");
    expect(stripUrl("https://x.test/" + "a".repeat(1000)).length).toBeLessThanOrEqual(512);
    expect(normaliseReport({}).effectiveDirective).toBe("");
  });
});
