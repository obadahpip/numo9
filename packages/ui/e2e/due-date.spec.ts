import { expect, test } from "@playwright/test";

/**
 * D-01-T17 (gap-12 on documents): the due date is required — saving without one shows the error
 * and doesn't save; the term chips set the date from the document date, and the helper says when
 * it is due.
 */
const STORY = "/iframe.html?id=forms-pickers--due-date&viewMode=story";

test("can't save without a due date; chips set dates", async ({ page }) => {
  await page.goto(STORY);
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("alert")).toHaveText("Enter a due date.");
  await expect(page.getByRole("status")).toHaveText("");

  await page.getByRole("button", { name: "Net 30" }).click();
  await expect(page.getByRole("textbox", { name: "Due date" })).toHaveValue("14 Aug 2026");
  await expect(page.getByText("Due in 30 days")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);

  await page.getByRole("button", { name: "20th of next month" }).click();
  await expect(page.getByRole("textbox", { name: "Due date" })).toHaveValue("20 Aug 2026");
  await expect(page.getByText("Due in 36 days")).toBeVisible();

  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Saved — due 2026-08-20");
});
