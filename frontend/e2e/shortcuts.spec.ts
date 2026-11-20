import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * A-09-T08 — keyboard shortcuts: `?` opens the sheet listing every shortcut; `N C` opens a new
 * contact; the quick-create buttons show their shortcut inline (every quick-create shows its
 * shortcut); a single key typed in a field does nothing.
 */
const ORG = "acme";

test.use({ viewport: { width: 1440, height: 900 } });

test("? sheet, N C opens a new contact, inline hints, nothing while typing", async ({ page }) => {
  await mockCsrf(page);
  await page.route("**/api/v1/o/acme/contacts?*", (route) =>
    route.fulfill({ json: { count: 0, page: 1, page_size: 50, results: [], counts: {} } }),
  );
  await page.goto(`/o/${ORG}/contacts`);
  const newContact = page.getByRole("link", { name: "New contact" }).last();
  await expect(newContact.locator("kbd")).toHaveText("N C");

  await page.locator("body").press("?");
  const sheet = page.getByRole("dialog", { name: "Keyboard shortcuts" });
  await expect(sheet).toBeVisible();
  const create = sheet.getByRole("table", { name: "Create (press N, then the letter)" });
  await expect(create.locator("kbd")).toHaveText([
    "N I",
    "N B",
    "N C",
    "N Q",
    "N P",
    "N J",
    "N S",
    "N R",
    "N T",
    "N U",
  ]);
  await expectAccessible(page);
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();

  await page.keyboard.press("n");
  await page.keyboard.press("c");
  await expect(page).toHaveURL(`/o/${ORG}/contacts/new`);

  const field = page.getByRole("textbox").first();
  await field.focus();
  await page.keyboard.type("?nc");
  await expect(sheet).toBeHidden();
  await expect(page).toHaveURL(`/o/${ORG}/contacts/new`);
});
