import { expect, test } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * U-06-T12 — feature flags admin (`/console/flags`): switch a flag per organisation and by
 * percentage. Fixtures in the API's shape (backend/numo9/platform/flags.py; that toggles reflect
 * in /me/flags: backend/tests/test_platform_flags.py).
 */
test("turn a flag on for one organisation and a percentage", async ({ page }) => {
  await mockCsrf(page);
  let flag = {
    name: "payroll.t4_screen",
    note: "New T4 screen",
    mode: "off",
    percent: null as string | null,
    organisations: [] as { id: string; name: string }[],
    practices: [],
    users: [],
    updated_at: "2026-11-18T15:00:00Z",
  };
  const patches: Record<string, unknown>[] = [];
  await page.route("**/api/v1/platform/flags", (r) => r.fulfill({ json: { flags: [flag] } }));
  await page.route("**/api/v1/platform/flags/payroll.t4_screen", (r) => {
    const body = jsonBody(r);
    patches.push(body);
    flag = {
      ...flag,
      ...(body.mode ? { mode: String(body.mode) } : {}),
      ...("percent" in body ? { percent: body.percent as string } : {}),
      ...(body.organisations
        ? { organisations: [{ id: "org-1", name: "Maple Leaf Supply" }] }
        : {}),
    };
    return r.fulfill({ json: flag });
  });
  await page.route("**/api/v1/platform/organisations?*", (r) =>
    r.fulfill({ json: { results: [{ id: "org-1", name: "Maple Leaf Supply" }] } }),
  );

  await page.goto("/console/flags");
  const card = page.locator('[data-flag="payroll.t4_screen"]');
  await card.getByRole("button", { name: "By rule" }).click();
  await card.getByLabel("Add an organisation").fill("Maple");
  await card.getByRole("button", { name: "Add Maple Leaf Supply" }).click();
  await expect(card.getByRole("button", { name: "Remove Maple Leaf Supply" })).toBeVisible();
  await card.getByLabel("Percentage of organisations").fill("10");
  await card.getByRole("button", { name: "Save percentage" }).click();
  await expect.poll(() => patches.at(-1)).toEqual({ percent: "10" });
  expect(patches[0]).toEqual({ mode: "rules" });
  expect(patches[1]).toEqual({ organisations: ["org-1"] });
  await expectAccessible(page);
});
