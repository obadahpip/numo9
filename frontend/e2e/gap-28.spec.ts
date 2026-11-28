import { expect, test } from "@playwright/test";

import { jsonBody } from "./auth-helpers";
import { bankRule, mockBuilderData, mockRules, ORG, previewLine } from "./bank-rules-fixtures";

/**
 * gap-28 (F-04-T16) — bank rules better than Xero: regex conditions with a tester, "does not
 * contain", amount ranges, explicit priority (first match wins) and the history preview naming
 * the shadowing rule. Backend side: backend/tests/test_bank_rule_gap28.py (@gap-28 on the API).
 */
test("@gap-28 regex, does-not-contain and amount range in the builder, with the preview", async ({
  page,
}) => {
  await mockBuilderData(page);
  const previews: Record<string, unknown>[] = [];
  await page.route("**/api/v1/o/acme/bank-rules/preview", async (route) => {
    previews.push(jsonBody(route));
    await route.fulfill({
      json: {
        since: "2026-03-12",
        days: 90,
        applies: 1,
        shadowed: 1,
        truncated: false,
        rows: [
          {
            line: previewLine("l1", "PETRO-CANADA 12", "-45.00"),
            outcome: "applies",
            shadowed_by: null,
            also_matches: [],
          },
          {
            line: previewLine("l2", "PETRO-CANADA 99", "-180.00"),
            outcome: "shadowed",
            shadowed_by: { id: "r1", name: "Fleet cards" },
            also_matches: [],
          },
        ],
      },
    });
  });
  const created: Record<string, unknown>[] = [];
  await page.route("**/api/v1/o/acme/bank-rules", async (route) => {
    created.push(jsonBody(route));
    await route.fulfill({ status: 201, json: bankRule({ id: "r9" }) });
  });
  await page.route(/\/api\/v1\/o\/acme\/bank-rules\?.*$/, (route) =>
    route.fulfill({ json: { results: [] } }),
  );

  await page.goto(`/o/${ORG}/banking/rules/new?type=spend`);
  await page.getByLabel("Rule name").fill("Fuel — not car wash");
  // Regex with the tester.
  await page.getByLabel("Condition 1: comparison").selectOption("regex");
  await page.getByLabel("Condition 1: pattern").fill("petro.?canada\\s+\\d+");
  await page.getByLabel("Test condition 1 on a sample text").fill("POS PETRO-CANADA 12 TORONTO");
  await expect(page.locator("[data-highlighted] mark")).toHaveText(["PETRO-CANADA 12"]);
  // Does not contain.
  await page.getByRole("button", { name: "Add a condition" }).click();
  await page.getByLabel("Condition 2: comparison").selectOption("not_contains");
  await page.getByLabel("Condition 2: value").fill("car wash");
  // Amount range: two fields.
  await page.getByRole("button", { name: "Add a condition" }).click();
  await page.getByLabel("Condition 3: field").selectOption("amount");
  await page.getByLabel("Condition 3: comparison").selectOption("between");
  await page.getByLabel("Condition 3: lowest amount").fill("20");
  await page.getByLabel("Condition 3: highest amount").fill("200");
  // Preview: the shadowing rule is named.
  const panel = page.locator("[data-preview]");
  await expect(panel.getByText("Shadowed by Fleet cards")).toBeVisible();
  expect(previews.at(-1)).toMatchObject({
    rule: {
      conditions: [
        { field: "description", operator: "regex", value: "petro.?canada\\s+\\d+" },
        { field: "description", operator: "not_contains", value: "car wash" },
        { field: "amount", operator: "between", value: "20", value_to: "200" },
      ],
    },
  });
  // Allocation at 100 %, then save.
  await page.getByLabel("Line 1: account").selectOption({ label: "5100 · Fuel" });
  await page.getByLabel("Line 1: tax code").selectOption("purchase.ON.standard");
  await page.getByRole("button", { name: "Save rule" }).click();
  await expect.poll(() => created.length).toBe(1);
  expect(created[0]).toMatchObject({
    name: "Fuel — not car wash",
    allocations: [{ percent: "100", tax_code: "purchase.ON.standard" }],
  });
});

test("@gap-28 explicit priority: the order set by drag is what the server keeps", async ({
  page,
}) => {
  const state = await mockRules(page, [
    bankRule({ id: "r1", name: "Fleet cards", priority: 1 }),
    bankRule({
      id: "r2",
      name: "Fuel — not car wash",
      priority: 2,
      conditions: [{ field: "description", operator: "regex", value: "petro", value_to: "" }],
    }),
  ]);
  await page.goto(`/o/${ORG}/banking/rules`);
  const handle = page.getByRole("button", { name: "Move Fuel — not car wash" });
  await expect(handle).toBeVisible();
  await handle.focus();
  for (const key of ["Space", "ArrowUp", "Space"]) {
    await page.keyboard.press(key);
    await page.waitForTimeout(200);
  }
  await expect.poll(() => state.reorders).toBe(1);
  await page.reload();
  await expect(page.locator("li[data-rule]").first()).toHaveAttribute(
    "aria-label",
    "Fuel — not car wash",
  );
});
