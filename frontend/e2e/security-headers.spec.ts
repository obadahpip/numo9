import { expect, test } from "@playwright/test";

/**
 * S-03-T10 acceptance: every kind of response from the production build carries the security
 * headers (securityheaders.com set). CI also grades the running app with
 * tools/ci/check_security_headers.py (Security workflow, job `security-headers`).
 */
const RESPONSES = [
  { name: "page", path: "/o/acme/home", csp: /script-src 'self' 'nonce-/ },
  { name: "404 page", path: "/o/acme/no-such-screen", csp: /script-src 'self' 'nonce-/ },
  { name: "API route", path: "/api/csp-report", csp: /^default-src 'none'/ },
];

for (const { name, path, csp } of RESPONSES) {
  test(`security headers: ${name} (${path})`, async ({ request }) => {
    const response = await request.get(path, { maxRedirects: 0 });
    const headers = response.headers();
    expect(headers["content-security-policy"]).toMatch(csp);
    expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
    expect(headers["x-frame-options"]).toBe("DENY");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["permissions-policy"]).toContain("camera=(), display-capture=()");
    expect(headers["permissions-policy"]).toContain("microphone=()");
    expect(headers["cross-origin-opener-policy"]).toBe("same-origin");
    expect(headers["strict-transport-security"]).toMatch(/max-age=31536000; includeSubDomains/);
    expect(headers["x-powered-by"]).toBeUndefined();
  });
}

test("security headers: static assets carry nosniff", async ({ page, request }) => {
  await page.goto("/o/acme/home");
  const src = await page.locator("script[src^='/_next/static/']").first().getAttribute("src");
  const response = await request.get(src!);
  expect(response.ok()).toBe(true);
  expect(response.headers()["x-content-type-options"]).toBe("nosniff");
});
