import { expect, test, type Page } from "@playwright/test";

import { TEARDOWN_FINDINGS, TEARDOWN_SUMMARY } from "../src/accounting/assurance/fixtures";
import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * K-09-T21 — Assurance page on the teardown-style fixture (REFINED): the score card, at least
 * seven rule groups with their explanations, severity chips filtering the list, Propose fix
 * showing the draft Dr Petty Cash / Cr Shareholder Loan and creating it, Mark false positive
 * asking for a reason. Server side: backend/tests/test_assurance_*.py.
 */
const ORG = "refined";
const API = `**/api/v1/o/${ORG}/assurance`;

async function mockAssurance(page: Page) {
  const sent: { url: string; body: Record<string, unknown> }[] = [];
  await mockCsrf(page);
  await page.route(`${API}/`, (r) => r.fulfill({ json: TEARDOWN_SUMMARY }));
  await page.route(`${API}/findings*`, (r) => {
    const url = new URL(r.request().url());
    const severities = url.searchParams.getAll("severity");
    const findings = severities.length
      ? TEARDOWN_FINDINGS.filter((f) => severities.includes(f.severity))
      : TEARDOWN_FINDINGS;
    return r.fulfill({ json: { count: findings.length, findings } });
  });
  await page.route(`${API}/findings/neg-cash/fix`, (r) => {
    if (r.request().method() === "POST") {
      sent.push({ url: "fix", body: jsonBody(r) });
      return r.fulfill({
        status: 201,
        json: { draft: { id: "draft-1", status: "draft" }, finding: TEARDOWN_FINDINGS[0] },
      });
    }
    return r.fulfill({
      json: {
        fix: {
          kind: "journal",
          reasoning:
            "Petty Cash fell to −994.17 on 15 Jun 2026 and no other bank account can cover it: the owner most likely paid personally.",
          date: "2026-06-03",
          narration: "Owner funded Petty Cash",
          lines: [
            {
              account: "acc-1000",
              code: "1000",
              label: "1000 · Petty Cash",
              debit: "994.17",
              credit: "0.00",
              description: "",
            },
            {
              account: "acc-2900",
              code: "2900",
              label: "2900 · Shareholder Loan",
              debit: "0.00",
              credit: "994.17",
              description: "",
            },
          ],
          recode: null,
          alternatives: [],
        },
      },
    });
  });
  await page.route(`${API}/findings/*/false-positive`, (r) => {
    sent.push({ url: "false-positive", body: jsonBody(r) });
    return r.fulfill({ json: { ...TEARDOWN_FINDINGS[8], status: "false_positive" } });
  });
  return sent;
}

test.use({ viewport: { width: 1440, height: 900 } });

test("teardown fixture shows at least seven rule groups", async ({ page }) => {
  await mockAssurance(page);
  await page.goto(`/o/${ORG}/accounting/assurance`);
  await expect(page.locator("[data-assurance-score]")).toContainText("20 out of 100");
  const groups = page.locator("[data-rule-group]");
  expect(await groups.count()).toBeGreaterThanOrEqual(7);
  await expect(page.locator('[data-rule-group="NEG_CASH"]')).toContainText(
    "Petty Cash went below zero",
  );
  await page.locator('[data-severity-chip="critical"]').click();
  await expect(groups).toHaveCount(3);
  await expectAccessible(page);
});

test("propose fix shows the draft entry and creates it", async ({ page }) => {
  const sent = await mockAssurance(page);
  await page.goto(`/o/${ORG}/accounting/assurance`);
  await page
    .locator('[data-rule-group="NEG_CASH"]')
    .getByRole("button", { name: "Propose fix" })
    .click();
  const dialog = page.getByRole("dialog", { name: "Proposed fix" });
  await expect(dialog.locator("[data-fix-lines] tbody tr")).toHaveCount(2);
  await expect(dialog).toContainText("the owner most likely paid personally");
  await dialog.getByRole("button", { name: "Create draft journal" }).click();
  await expect(dialog.getByRole("link", { name: "Open the draft" })).toBeVisible();
  expect(sent.map((s) => s.url)).toEqual(["fix"]);
});

test("mark false positive asks for a reason", async ({ page }) => {
  const sent = await mockAssurance(page);
  await page.goto(`/o/${ORG}/accounting/assurance`);
  await page
    .locator('[data-rule-group="BACKDATED"]')
    .getByRole("button", { name: "Mark false positive" })
    .click();
  const dialog = page.getByRole("dialog", { name: "Mark as a false positive" });
  await expect(dialog.getByRole("button", { name: "Save" })).toBeDisabled();
  await dialog.getByLabel("Reason").fill("Imported from Xero");
  await dialog.getByRole("button", { name: "Save" }).click();
  await expect(dialog).toBeHidden();
  expect(sent[0]).toEqual({ url: "false-positive", body: { reason: "Imported from Xero" } });
});
