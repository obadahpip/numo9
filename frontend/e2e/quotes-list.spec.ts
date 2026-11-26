import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { ORG, savedQuote } from "./quotes-fixtures";

/**
 * D-02-T14 (gap-05) — the quotes list tabs All / Draft / Sent / Accepted / Declined / Expired /
 * Invoiced show the server's counts, summed from its counts per QuoteStatus — the same numbers
 * the overview card reads (`quotes.status_counts`); a tab lists as many quotes as it counts.
 * Server side: backend/tests/test_quote_tabs.py.
 */
const counts = { draft: 2, sent: 1, viewed: 1, accepted: 1, declined: 0, expired: 1, invoiced: 0 };
const tabs = { all: 6, draft: 2, sent: 2, accepted: 1, declined: 0, expired: 1, invoiced: 0 };

test("tab counts are the status counts and each tab lists its quotes", async ({ page }) => {
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/quotes?*`, (route) => {
    const tab = new URL(route.request().url()).searchParams.get("tab") ?? "all";
    const n = tabs[tab as keyof typeof tabs];
    const status = tab === "all" || tab === "sent" ? "sent" : tab;
    const results = Array.from({ length: n }, (_, i) =>
      savedQuote({
        id: `2a2a2a2a-0000-4000-8000-00000000000${i}`,
        number: `QU-000${i + 1}`,
        status,
      }),
    );
    return route.fulfill({ json: { count: n, page: 1, pages: 1, counts, tabs, results } });
  });
  await page.goto(`/o/${ORG}/sales/quotes`);
  await expect(page.getByRole("heading", { name: "Quotes" })).toBeVisible();
  const list = page.getByRole("tablist", { name: "Quotes by status" });
  for (const [tab, label] of [
    ["all", "All"],
    ["draft", "Draft"],
    ["sent", "Sent"],
    ["accepted", "Accepted"],
    ["declined", "Declined"],
    ["expired", "Expired"],
    ["invoiced", "Invoiced"],
  ] as const) {
    await expect(list.getByRole("tab", { name: new RegExp(`^${label}`) })).toContainText(
      String(tabs[tab]),
    );
  }
  await list.getByRole("tab", { name: /^Draft/ }).click();
  await expect(page.locator("[data-quote-row]")).toHaveCount(tabs.draft);
  await expectAccessible(page);
});
