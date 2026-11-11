import { expect, type Page, type Route } from "@playwright/test";

import { auditLabels, blocking, describeFindings, runAxe } from "../../packages/ui/e2e/a11y";

/**
 * Shared helpers for the authentication screen suites (A-02-T10…T12). The API is answered with
 * fixtures in the shape of the real one (django-allauth headless + Numo9 API, see
 * docs/architecture/authentication.md); the same flows were also run against the real backend
 * (NUMO9_BACKEND_URL) when the screens were built.
 */
export const AUTH = "**/_allauth/browser/v1";

export async function mockCsrf(page: Page): Promise<void> {
  await page.route("**/api/v1/auth/csrf", (route) =>
    route.fulfill({ json: { csrfToken: "test-csrf-token" } }),
  );
}

/** Body of a JSON request (fails the test when the CSRF header is missing on a POST). */
export function jsonBody(route: Route): Record<string, unknown> {
  const request = route.request();
  if (request.method() !== "GET") {
    expect(request.headers()["x-csrftoken"]).toBe("test-csrf-token");
  }
  return (request.postDataJSON() ?? {}) as Record<string, unknown>;
}

export function flows(...pending: string[]) {
  return { flows: pending.map((id) => ({ id, is_pending: true })) };
}

/** axe-core (0 serious/critical) + hidden-label audit, like the Phase 0 route suite. */
export async function expectAccessible(page: Page): Promise<void> {
  const findings = blocking(await runAxe(page));
  expect(findings, describeFindings(findings)).toEqual([]);
  expect(await auditLabels(page)).toEqual([]);
}

/** No horizontal scroll at the current viewport. */
export async function expectNoHorizontalScroll(page: Page): Promise<void> {
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth),
  ).toBeLessThanOrEqual(0);
}
