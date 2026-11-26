import { expect, test } from "@playwright/test";

import { expectAccessible } from "./auth-helpers";
import { CUSTOMER, ORG, QUOTE, mockQuoteEditor, savedQuote } from "./quotes-fixtures";

/**
 * D-02-T12 — the quote editor: a quote with two options (an optional line and an alternative
 * group) in under 90 seconds — customer, lines, the Optional toggle, the Alternative group
 * picker, the expiry date (30 days ahead by default) and a deposit. Server side:
 * backend/tests/test_quotes_api.py.
 */
test.use({ viewport: { width: 1440, height: 900 } });

test("create a quote with 2 options in under 90 s", async ({ page }) => {
  const state = await mockQuoteEditor(page);
  const started = Date.now();
  await page.goto(`/o/${ORG}/sales/quotes/new`);
  const form = page.getByRole("form", { name: "New quote" });
  await expect(form.getByRole("option", { name: "Maple Leaf Supply Ltd." })).toBeAttached();
  await form.getByRole("combobox", { name: "Customer" }).selectOption(CUSTOMER);
  await expect(form.getByLabel(/^Expiry date/)).not.toHaveValue("");
  await page.getByRole("textbox", { name: "Description, line 1" }).fill("Cabinets");
  await page.getByRole("textbox", { name: "Unit price, line 1" }).fill("1000");
  await page.getByRole("button", { name: "Add a line" }).click();
  await page.getByRole("textbox", { name: "Description, line 2" }).fill("Install");
  await page.getByRole("textbox", { name: "Unit price, line 2" }).fill("200");
  await page.getByRole("checkbox", { name: "Optional, line 2" }).check();
  await page.getByRole("button", { name: "Add a line" }).click();
  await page.getByRole("textbox", { name: "Description, line 3" }).fill("Oak doors");
  await page.getByRole("textbox", { name: "Unit price, line 3" }).fill("500");
  await page.getByRole("combobox", { name: "Alternative group, line 3" }).fill("Wood");
  await page.getByRole("button", { name: "Add a line" }).click();
  await page.getByRole("textbox", { name: "Description, line 4" }).fill("Walnut doors");
  await page.getByRole("textbox", { name: "Unit price, line 4" }).fill("800");
  await page.getByRole("combobox", { name: "Alternative group, line 4" }).fill("Wood");
  await page.keyboard.press("Tab");
  // Only the plain line and the first alternative count: $1,500.00.
  await expect(page.locator('[data-total="total"]')).toContainText("$1,500.00");
  await expectAccessible(page);
  await form.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("Draft saved.")).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/sales/quotes/${QUOTE}$`));
  expect(Date.now() - started).toBeLessThan(90_000);
  expect(state.posts[0]).toMatchObject({
    path: "POST ",
    body: {
      customer: CUSTOMER,
      lines: [
        { description: "Cabinets" },
        { description: "Install", is_optional: true, selected: false },
        { description: "Oak doors", alternative_group: "Wood", selected: true },
        { description: "Walnut doors", alternative_group: "Wood", selected: false },
      ],
    },
  });
});

test("a sent quote opens read-only with its actions", async ({ page }) => {
  await mockQuoteEditor(page, savedQuote({ status: "sent", status_label: "Sent" }));
  await page.goto(`/o/${ORG}/sales/quotes/${QUOTE}`);
  await expect(page.getByRole("heading", { name: "Quote QU-0001" })).toBeVisible();
  await expect(page.getByRole("note")).toContainText("This quote is sent");
  await expect(page.getByRole("checkbox", { name: "Optional, line 2" })).toBeDisabled();
  const bar = page.getByRole("toolbar", { name: "Quote actions" });
  await expect(bar.getByRole("button", { name: "Mark accepted" })).toBeVisible();
  await expect(bar.getByRole("button", { name: "Copy link" })).toBeVisible();
  await expectAccessible(page);
});
