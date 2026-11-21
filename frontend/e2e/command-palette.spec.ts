import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";
import { entitlements, mockEntitlements, WITHOUT_ACCOUNTING } from "./entitlements-fixtures";

/**
 * A-09-T07 — command palette, keyboard only: Ctrl+K opens it with focus in the box; typing
 * searches the organisation; results come grouped (Records, Settings, …); a gated item stays with
 * its reason in words; ↓/Enter opens; the pick shows under Recent next time; Esc closes and focus
 * returns. axe: 0 serious/critical with results open.
 */
const MAPLE = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";

async function mockSearch(page: Page): Promise<string[]> {
  const queries: string[] = [];
  await page.route(`**/api/v1/o/${MAPLE}/my-permissions`, (route) =>
    route.fulfill({
      json: { permissions: ["contacts.contacts.manage", "organisation.members.invite"] },
    }),
  );
  await page.route(`**/api/v1/o/${MAPLE}/search?*`, (route) => {
    const q = new URL(route.request().url()).searchParams.get("q") ?? "";
    queries.push(q);
    return route.fulfill({
      json: {
        query: q,
        records: [
          {
            type: "ledger.journalentry",
            id: "j-1",
            title: "MJ-0042 · Year-end accrual",
            subtitle: "Journal · 2026-03-31",
            code: "MJ-0042",
            amount: "1130.00",
            date: "2026-03-31",
            url: `/o/${MAPLE}/accounting/journals/j-1`,
            match: "text",
            locked: true,
            reason: "Part of Accounting, which isn't in this organisation's package.",
          },
        ],
        settings: [
          {
            key: "lock_dates",
            title: "Lock dates",
            url: `/o/${MAPLE}/settings/lock-dates`,
            locked: false,
            reason: null,
          },
        ],
        reports: [],
        navigation: [],
      },
    });
  });
  return queries;
}

test.use({ viewport: { width: 1440, height: 900 } });

test("keyboard only: open, search, gated item explained, open a result, recents", async ({
  page,
}) => {
  await mockCsrf(page);
  await mockEntitlements(page, MAPLE, entitlements(WITHOUT_ACCOUNTING));
  const queries = await mockSearch(page);
  await page.goto(`/o/${MAPLE}/settings/general`);
  await expect(page.getByRole("button", { name: /Search or jump to/ })).toBeVisible();
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: "Search" });
  await expect(dialog).toBeVisible();
  const box = dialog.getByRole("combobox", {
    name: "Search contacts, accounts, journals, settings and reports",
  });
  await expect(box).toBeFocused();

  // Nothing typed yet: the quick-create actions; "New contact" is locked (no Accounting).
  const create = dialog.getByRole("group", { name: "Create" });
  await expect(create.getByRole("option", { name: /New contact/ })).toContainText(
    "Accounting isn't in this organisation's package",
  );
  await expect(create.getByRole("option", { name: /Invite a user/ })).toContainText("N U");

  await page.keyboard.type("lock date");
  await expect(dialog.getByRole("group", { name: "Settings" })).toBeVisible();
  expect(queries.at(-1)).toBe("lock date");
  await expect(dialog.getByRole("group", { name: "Records" }).getByRole("option")).toContainText(
    "Part of Accounting, which isn't in this organisation's package.",
  );
  await expectAccessible(page);

  const options = dialog.getByRole("option");
  await expect(options.first()).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("ArrowDown");
  await expect(dialog.getByRole("option", { name: /Lock dates/ })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(`/o/${MAPLE}/settings/lock-dates`);
  await expect(dialog).toBeHidden();

  await page.keyboard.press("Control+k");
  await expect(dialog.getByRole("group", { name: "Recent" })).toContainText("Lock dates");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});
