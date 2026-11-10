import { API_CSP, HSTS, PERMISSIONS_POLICY, headerRules, securityHeaders } from "./headers";

function asMap(production: boolean): Map<string, string> {
  return new Map(securityHeaders({ production }).map(({ key, value }) => [key, value]));
}

describe("security headers (S-03-T10)", () => {
  it("sends the securityheaders.com set on every response", () => {
    const headers = asMap(true);
    expect(headers.get("X-Frame-Options")).toBe("DENY");
    expect(headers.get("X-Content-Type-Options")).toBe("nosniff");
    expect(headers.get("Referrer-Policy")).toBe("strict-origin-when-cross-origin");
    expect(headers.get("Cross-Origin-Opener-Policy")).toBe("same-origin");
    expect(headers.get("Strict-Transport-Security")).toBe(HSTS);
  });

  it("HSTS is one year with subdomains, production builds only", () => {
    expect(HSTS).toMatch(/max-age=31536000; includeSubDomains/);
    expect(asMap(false).has("Strict-Transport-Security")).toBe(false);
  });

  it("Permissions-Policy turns powerful features off, payment only for Stripe", () => {
    for (const feature of ["camera", "microphone", "geolocation", "usb", "display-capture"]) {
      expect(PERMISSIONS_POLICY).toContain(`${feature}=()`);
    }
    expect(PERMISSIONS_POLICY).toContain('payment=(self "https://js.stripe.com")');
  });

  it("API routes get a data-only policy; pages keep the middleware's nonce CSP", () => {
    const rules = headerRules(true);
    const all = rules.find((r) => r.source === "/:path*")!;
    expect(all.headers.some((h) => h.key === "Content-Security-Policy")).toBe(false);
    const api = rules.find((r) => r.source === "/api/:path*")!;
    expect(api.headers).toEqual([{ key: "Content-Security-Policy", value: API_CSP }]);
    expect(API_CSP).toContain("default-src 'none'");
    expect(API_CSP).toContain("frame-ancestors 'none'");
  });
});
