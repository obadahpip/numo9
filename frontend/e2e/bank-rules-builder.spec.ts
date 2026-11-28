import { expect, test } from "@playwright/test";

import { expectAccessible, jsonBody } from "./auth-helpers";
import { ruleFromLineHref } from "../src/banking/rules/fromLine";
import { mockBuilderData, ORG, previewLine } from "./bank-rules-fixtures";

/**
 * F-04-T13 — preview panel in the rule builder: the affected historical lines and the shadowing
 * rules. Acceptance: the panel shows the shadowed-by rule name. (The preview itself — count =
 * apply count — is tested on the real API in backend/tests/test_bank_rule_preview.py.)
 */
test("preview panel lists affected lines and the shadowing rule", async ({ page }) => {
  await mockBuilderData(page);
  const sent: Record<string, unknown>[] = [];
  await page.route("**/api/v1/o/acme/bank-rules/preview", async (route) => {
    sent.push(jsonBody(route));
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
            line: previewLine("l2", "PETRO big fill", "-150.00"),
            outcome: "shadowed",
            shadowed_by: { id: "r1", name: "Big fuel" },
            also_matches: [],
          },
        ],
      },
    });
  });
  await page.goto(`/o/${ORG}/banking/rules/new?type=spend`);
  await expect(page.getByRole("heading", { name: "New bank rule", level: 1 })).toBeVisible();
  const panel = page.locator("[data-preview]");
  await expect(
    panel.getByText("Complete the conditions to see which lines the rule matches."),
  ).toBeVisible();
  await page.getByLabel("Condition 1: value").fill("PETRO");
  await expect(panel.getByText("Shadowed by Big fuel")).toBeVisible();
  await expect(panel.getByText("Coded by this rule", { exact: true })).toBeVisible();
  await expect(
    panel.getByText("1 line would be coded by this rule; 1 is taken by a higher rule."),
  ).toBeVisible();
  expect(sent.at(-1)).toMatchObject({
    days: 90,
    rule: { conditions: [{ field: "description", operator: "contains", value: "PETRO" }] },
  });
  await expectAccessible(page);
});

/**
 * F-04-T14 — "Create rule from line": the action's link (``ruleFromLineHref``, what
 * ``CreateRuleFromLineAction`` renders on a statement line) opens the builder pre-filled with the
 * payee / description condition, the line's type and bank account.
 */
test("create rule from a statement line opens the builder pre-filled", async ({ page }) => {
  await mockBuilderData(page);
  await page.route("**/api/v1/o/acme/bank-rules/preview", (route) =>
    route.fulfill({
      json: { since: "", days: 90, applies: 1, shadowed: 0, truncated: false, rows: [] },
    }),
  );
  const href = ruleFromLineHref(ORG, {
    id: "line-1",
    amount: "-45.10",
    payee: "",
    description: "PETRO-CANADA #1234 TORONTO",
    bank_account: "b1",
  });
  await page.goto(href);
  await expect(page.getByRole("heading", { name: "New bank rule", level: 1 })).toBeVisible();
  await expect(page.getByLabel("Rule name")).toHaveValue("PETRO-CANADA TORONTO");
  await expect(page.getByLabel("Rule type")).toHaveValue("spend");
  await expect(page.getByLabel("Condition 1: field")).toHaveValue("description");
  await expect(page.getByLabel("Condition 1: comparison")).toHaveValue("contains");
  await expect(page.getByLabel("Condition 1: value")).toHaveValue("PETRO-CANADA TORONTO");
  await expect(page.getByRole("checkbox", { name: "TD Business Chequing" })).toBeChecked();

  await page.goto(
    ruleFromLineHref(ORG, { amount: "250.00", payee: "Shopify Payments", description: "DEP" }),
  );
  await expect(page.getByLabel("Rule type")).toHaveValue("receive");
  await expect(page.getByLabel("Condition 1: field")).toHaveValue("payee");
  await expect(page.getByLabel("Condition 1: value")).toHaveValue("Shopify Payments");
});
