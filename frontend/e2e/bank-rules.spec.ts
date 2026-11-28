import { expect, test } from "@playwright/test";

import { expectAccessible } from "./auth-helpers";
import { bankRule, mockRules, ORG } from "./bank-rules-fixtures";

/**
 * F-04-T10 — bank rules list: drag-to-reorder (dnd-kit, keyboard here: Space, arrow, Space),
 * on/off toggle, "applied N times" counters, search. Acceptance: the order persists after a
 * reload (the stateful mock keeps what the reorder endpoint received).
 */
const RULES = [
  bankRule({ id: "r1", name: "Petro-Canada fuel", priority: 1 }),
  bankRule({
    id: "r2",
    name: "Tim Hortons",
    priority: 2,
    conditions: [{ field: "payee", operator: "starts_with", value: "TIM", value_to: "" }],
    applied_count: 3,
    last_applied_at: "2026-06-15T14:00:00Z",
    auto_apply: true,
  }),
  bankRule({
    id: "r3",
    name: "Bell Canada",
    priority: 3,
    conditions: [{ field: "payee", operator: "equals", value: "Bell", value_to: "" }],
  }),
  bankRule({ id: "r4", name: "Interest", type: "receive", priority: 1 }),
];

function names(page: import("@playwright/test").Page) {
  return page
    .locator("li[data-rule]")
    .evaluateAll((items) => items.map((item) => item.getAttribute("aria-label")));
}

test("reorder by keyboard drag persists after reload", async ({ page }) => {
  const state = await mockRules(page, RULES);
  await page.goto(`/o/${ORG}/banking/rules`);
  await expect(page.getByRole("heading", { name: "Bank rules", level: 1 })).toBeVisible();
  await expect.poll(() => names(page)).toEqual(["Petro-Canada fuel", "Tim Hortons", "Bell Canada"]);
  const tim = page.getByRole("listitem", { name: "Tim Hortons" });
  await expect(tim.getByText("Applied 3 times · last 15 Jun 2026")).toBeVisible();
  await expect(tim.getByText("Auto-apply")).toBeVisible();
  await expect(
    page.getByRole("listitem", { name: "Bell Canada" }).getByText("Not applied yet"),
  ).toBeVisible();
  await expectAccessible(page);

  const handle = page.getByRole("button", { name: "Move Bell Canada" });
  await handle.focus();
  // dnd-kit measures the list after pick-up: give each key a moment.
  for (const key of ["Space", "ArrowUp", "ArrowUp", "Space"]) {
    await page.keyboard.press(key);
    await page.waitForTimeout(200);
  }
  await expect.poll(() => state.reorders).toBe(1);
  await expect.poll(() => names(page)).toEqual(["Bell Canada", "Petro-Canada fuel", "Tim Hortons"]);

  await page.reload();
  await expect.poll(() => names(page)).toEqual(["Bell Canada", "Petro-Canada fuel", "Tim Hortons"]);
  await expect(
    page.getByRole("listitem", { name: "Bell Canada" }).getByText("Priority 1"),
  ).toBeAttached();
});

test("pointer drag, toggle, search and type tabs", async ({ page }) => {
  const state = await mockRules(page, RULES);
  await page.goto(`/o/${ORG}/banking/rules`);
  await expect.poll(() => names(page)).toEqual(["Petro-Canada fuel", "Tim Hortons", "Bell Canada"]);

  const from = await page.getByRole("button", { name: "Move Petro-Canada fuel" }).boundingBox();
  const to = await page.getByRole("button", { name: "Move Bell Canada" }).boundingBox();
  await page.mouse.move(from!.x + from!.width / 2, from!.y + from!.height / 2);
  await page.mouse.down();
  await page.mouse.move(from!.x + from!.width / 2, to!.y + to!.height / 2 + 10, { steps: 12 });
  await page.mouse.up();
  await expect.poll(() => state.reorders).toBe(1);
  await expect.poll(() => names(page)).toEqual(["Tim Hortons", "Bell Canada", "Petro-Canada fuel"]);

  await page.getByRole("switch", { name: "Tim Hortons on" }).click();
  await expect.poll(() => state.rules.find((r) => r.id === "r2")!.active).toBe(false);
  await expect(page.getByRole("listitem", { name: "Tim Hortons" }).getByText("Off")).toBeVisible();

  await page.getByLabel("Search rules").fill("petro");
  await expect.poll(() => names(page)).toEqual(["Petro-Canada fuel"]);
  await expect(page.getByRole("button", { name: "Move Petro-Canada fuel" })).toBeDisabled();
  await page.getByLabel("Search rules").fill("");

  await page.getByRole("button", { name: "Receive money" }).click();
  await expect.poll(() => names(page)).toEqual(["Interest"]);
});
