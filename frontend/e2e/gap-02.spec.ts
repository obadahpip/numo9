import { expect, test, type APIRequestContext } from "@playwright/test";

import { GAP_02_PATHS } from "./gap-02.paths";

const MAX_HOPS = 5;

interface Hop {
  url: string;
  status: number;
}

/** Follow redirects one hop at a time so every intermediate status is visible. */
async function crawl(request: APIRequestContext, path: string, org?: string): Promise<Hop[]> {
  const headers: Record<string, string> = org ? { cookie: `numo9_org=${org}` } : {};
  const hops: Hop[] = [];
  let url = path;
  for (let i = 0; i <= MAX_HOPS; i++) {
    const response = await request.get(url, { maxRedirects: 0, headers });
    hops.push({ url, status: response.status() });
    const location = response.headers()["location"];
    if (response.status() < 300 || response.status() >= 400 || !location) return hops;
    const next = new URL(location, "http://placeholder");
    url = `${next.pathname}${next.search}`;
  }
  throw new Error(`more than ${MAX_HOPS} redirects from ${path}: ${JSON.stringify(hops)}`);
}

test.describe("gap-02: root and legacy-style URLs never 404", () => {
  test("the crawl list has 40 paths", () => {
    expect(GAP_02_PATHS).toHaveLength(40);
  });

  for (const { path, final, org } of GAP_02_PATHS) {
    test(`${path}${org ? ` (org=${org})` : ""} → ${final}`, async ({ request }) => {
      const hops = await crawl(request, path, org);
      const last = hops.at(-1);

      expect(hops.map((hop) => hop.status)).not.toContain(404);
      expect(last?.status, JSON.stringify(hops)).toBe(200);
      expect(new URL(last?.url ?? "", "http://placeholder").pathname).toBe(final);
    });
  }
});

test.describe("gap-02: redirect semantics", () => {
  test("URL-only redirects are permanent (301)", async ({ request }) => {
    const [first] = await crawl(request, "/o/acme");
    expect(first?.status).toBe(301);
  });

  test("cookie-dependent redirects are temporary (307)", async ({ request }) => {
    const [first] = await crawl(request, "/dashboard", "acme");
    expect(first?.status).toBe(307);
  });

  test("the query string is kept", async ({ request }) => {
    const hops = await crawl(request, "/o/acme/dashboard?tab=overview");
    expect(hops.at(-1)?.url).toBe("/o/acme/home?tab=overview");
  });

  test("an invalid organisation cookie falls back to Home", async ({ request }) => {
    const hops = await crawl(request, "/settings", "..%2Fevil");
    expect(hops.at(-1)).toEqual({ url: "/", status: 200 });
  });
});

test.describe("gap-02: unknown pages", () => {
  // Static 404 (no matching route): the custom page is server-rendered as HTML.
  test("/no-such-page → custom 404 with search and Home link", async ({ request }) => {
    const response = await request.get("/no-such-page", { maxRedirects: 0 });
    expect(response.status()).toBe(404);
    const html = await response.text();
    expect(html).toContain("We can&#x27;t find that page");
    expect(html).toContain('role="search"');
    expect(html).toContain("Go to Home");
  });

  // notFound() inside a dynamic route: Next.js returns 404 and ships the same custom page in the
  // React payload, rendered by the browser (checked visually; see the PR's testing notes).
  for (const path of ["/o/acme/no-such-module", "/o/Bad_Slug/home"]) {
    test(`${path} → 404 carrying the custom not-found page`, async ({ request }) => {
      const response = await request.get(path, { maxRedirects: 0 });
      expect(response.status()).toBe(404);
      const html = await response.text();
      expect(html).toContain("We can't find that page");
      expect(html).toContain("NotFoundSearch");
      expect(html).toContain("Go to Home");
    });
  }
});
