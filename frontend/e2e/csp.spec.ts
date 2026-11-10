import { expect, test, type Page } from "@playwright/test";

import { GAP_02_PATHS } from "./gap-02.paths";

/**
 * S-03-T02 acceptance: every page is served with a nonce-based Content Security Policy, renders
 * without a single CSP violation, Stripe (js.stripe.com script and frames) loads, and anything
 * else from another origin is blocked and reported to /api/csp-report.
 * Stripe is answered locally (page.route) so the test does not depend on the network; the CSP
 * decision in the browser is the same.
 */
const ROUTES = [
  "/",
  ...new Set(GAP_02_PATHS.map((p) => p.final).filter((f) => f.startsWith("/o/"))),
  "/o/acme/no-such-screen",
];

async function collectViolations(page: Page): Promise<string[]> {
  const violations: string[] = [];
  page.on("console", (message) => {
    if (/Content Security Policy|Refused to/i.test(message.text())) violations.push(message.text());
  });
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (event) => {
      console.error(`Refused to load (CSP ${event.violatedDirective}): ${event.blockedURI}`);
    });
  });
  return violations;
}

for (const route of ROUTES) {
  test(`CSP: ${route} has a nonce policy and no violations`, async ({ page }) => {
    const violations = await collectViolations(page);
    const response = await page.goto(route);
    const policy = response!.headers()["content-security-policy"]!;
    expect(policy).toMatch(/script-src 'self' 'nonce-[A-Za-z0-9+/=]{20,}'/);
    expect(policy).not.toContain("'unsafe-inline' ");
    expect(policy).not.toMatch(/script-src[^;]*'unsafe-(inline|eval)'/);
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).toContain("report-uri /api/csp-report");

    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForLoadState("load");
    await page.waitForTimeout(300); // late client-side work (hydration, effects)
    // Every script Next.js rendered carries this response's nonce.
    const nonce = /'nonce-([^']+)'/.exec(policy)![1]!;
    const scripts = await page
      .locator("script")
      .evaluateAll((nodes) => nodes.map((n) => (n as HTMLScriptElement).nonce));
    expect(scripts.length).toBeGreaterThan(0);
    expect(new Set(scripts)).toEqual(new Set([nonce]));
    expect(violations).toEqual([]);
  });
}

test("CSP: a new nonce for every response", async ({ request }) => {
  const nonces = new Set<string>();
  for (let i = 0; i < 5; i += 1) {
    const policy = (await request.get("/o/acme/home")).headers()["content-security-policy"]!;
    nonces.add(/'nonce-([^']+)'/.exec(policy)![1]!);
  }
  expect(nonces.size).toBe(5);
});

test("CSP: Stripe loads; other origins are blocked and reported", async ({ page }) => {
  const violations = await collectViolations(page);
  await page.route("https://js.stripe.com/**", (route) =>
    route.request().resourceType() === "script"
      ? route.fulfill({ contentType: "text/javascript", body: "window.__stripeLoaded = true;" })
      : route.fulfill({ contentType: "text/html", body: "<p>stripe frame</p>" }),
  );
  await page.route("https://cdn.example.com/**", (route) =>
    route.fulfill({ contentType: "text/javascript", body: "window.__evilLoaded = true;" }),
  );
  const reported = page.waitForRequest(
    (r) => r.url().endsWith("/api/csp-report") && r.method() === "POST",
  );

  await page.goto("/o/acme/settings/general");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  const result = await page.evaluate(async () => {
    const load = (src: string) =>
      new Promise<string>((resolve) => {
        const script = document.createElement("script");
        script.src = src;
        script.onload = () => resolve("loaded");
        script.onerror = () => resolve("blocked");
        document.head.append(script);
      });
    const stripe = await load("https://js.stripe.com/v3/");
    const other = await load("https://cdn.example.com/tracker.js");
    const frame = document.createElement("iframe");
    frame.src = "https://js.stripe.com/v3/elements-inner-card.html";
    document.body.append(frame);
    await new Promise((r) => setTimeout(r, 500));
    const w = window as unknown as { __stripeLoaded?: boolean; __evilLoaded?: boolean };
    return { stripe, other, stripeRan: w.__stripeLoaded, otherRan: w.__evilLoaded ?? false };
  });

  expect(result).toEqual({ stripe: "loaded", other: "blocked", stripeRan: true, otherRan: false });
  const report = await reported;
  expect(report.postData()).toContain("cdn.example.com");
  // The only violation is the blocked third-party script (browser message + event listener).
  expect(violations.length).toBeGreaterThan(0);
  for (const violation of violations) expect(violation).toContain("cdn.example.com");
  expect(violations.join("\n")).not.toContain("stripe.com/");
});

test("CSP report endpoint accepts reports and rejects junk", async ({ request }) => {
  const legacy = await request.post("/api/csp-report", {
    headers: { "content-type": "application/csp-report" },
    data: JSON.stringify({
      "csp-report": {
        "document-uri": "https://app.numo9.ca/o/acme/home?token=secret",
        "blocked-uri": "https://cdn.example.com/x.js",
        "effective-directive": "script-src-elem",
      },
    }),
  });
  expect(legacy.status()).toBe(204);
  const junk = await request.post("/api/csp-report", {
    headers: { "content-type": "application/csp-report" },
    data: "not json",
  });
  expect(junk.status()).toBe(400);
  const huge = await request.post("/api/csp-report", {
    headers: { "content-type": "application/csp-report" },
    data: JSON.stringify({ "csp-report": { "blocked-uri": "x".repeat(20_000) } }),
  });
  expect(huge.status()).toBe(413);
});
