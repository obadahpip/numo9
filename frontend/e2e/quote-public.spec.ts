import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { TOKEN, publicQuote } from "./quotes-fixtures";

/**
 * D-02-T13 — the public quote page on a phone: the options recalculate the total live, the big
 * Accept button takes the typed name (the signature pad is optional) and the options chosen; an
 * expired quote shows the reason and "ask for a new quote", Accept disabled; axe clean on the
 * mobile viewport. Server side: backend/tests/test_quotes_api.py.
 */
test.use({ viewport: { width: 375, height: 812 } });

async function mockPublic(page: Page, quote: Record<string, unknown>) {
  await mockCsrf(page);
  const posts: { path: string; body: unknown }[] = [];
  await page.route("**/api/v1/q/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "POST") posts.push({ path, body: request.postDataJSON() });
    if (path.endsWith("/preview")) {
      return route.fulfill({
        json: {
          lines: {},
          subtotal: "1700.00",
          discount_total: "0.00",
          tax_total: "0.00",
          total: "1700.00",
          deposit: "0.00",
        },
      });
    }
    if (path.endsWith("/accept")) {
      return route.fulfill({
        json: publicQuote({
          status: "accepted",
          can_accept: false,
          reason: "accepted",
          accepted_by: "Jo Lee",
          total: "1700.00",
        }),
      });
    }
    return route.fulfill({ json: quote });
  });
  return posts;
}

test("options recalculate and the customer accepts with a typed name", async ({ page }) => {
  const posts = await mockPublic(page, publicQuote());
  await page.goto(`/q/${encodeURIComponent(TOKEN)}`);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("QU-0001");
  await expectAccessible(page);
  await page.getByRole("checkbox", { name: /Install/ }).check();
  await expect(page.locator("[data-public-total]")).toHaveText("$1,700.00");
  await page.getByRole("textbox", { name: /Your full name/ }).fill("Jo Lee");
  await page.getByRole("button", { name: "Accept for $1,700.00" }).click();
  await expect(page.getByText("Accepted by Jo Lee. Thank you!")).toBeVisible();
  expect(posts.find((p) => p.path.endsWith("/accept"))?.body).toMatchObject({
    typed_name: "Jo Lee",
    selections: { l2: true },
  });
});

test("an expired quote shows the reason and Accept is disabled", async ({ page }) => {
  await mockPublic(page, publicQuote({ status: "expired", can_accept: false, reason: "expired" }));
  await page.goto(`/q/${encodeURIComponent(TOKEN)}`);
  await expect(page.getByText(/This quote expired at the end of 2026-07-15/)).toBeVisible();
  await expect(page.getByText("Ask Refined Interiors Inc. for a new quote.")).toBeVisible();
  await expect(page.getByRole("button", { name: /Accept for/ })).toBeDisabled();
  await expectAccessible(page);
});
