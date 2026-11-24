import type { Page } from "@playwright/test";

/** The journal's account cell is an autocomplete (C-04-T09): type part of it, then pick. */
export async function pickAccount(page: Page, line: number, typed: string, name: RegExp) {
  const box = page.getByRole("combobox", { name: `Account, line ${line}` });
  await box.click();
  await box.fill(typed);
  await page.getByRole("option", { name }).click();
}
