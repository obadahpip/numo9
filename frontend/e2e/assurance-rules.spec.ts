import { expect, test, type Page } from "@playwright/test";

import { TEARDOWN_FINDINGS, TEARDOWN_SUMMARY } from "../src/accounting/assurance/fixtures";
import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * K-09-T23 — rule settings: toggle, severity and parameters validated against the rule's schema
 * inline; Save sends what changed; changing N (BACKDATED days 7 → 30) re-evaluates on the next
 * run — the backdated journal (12 days late) is no longer a finding. The API is mocked here; the
 * real re-evaluation is backend/tests/test_assurance_api.py::test_rules_settings_validated_and_used.
 */
const ORG = "refined";
const API = `**/api/v1/o/${ORG}/assurance`;

const param = (name: string, kind: string, label: string, def: unknown, extra = {}) => ({
  name,
  kind,
  label,
  default: def,
  minimum: null,
  maximum: null,
  choices: [],
  ...extra,
});

function rules(days: number, roundOn: boolean) {
  return [
    {
      code: "BACKDATED",
      name: "Backdated posting",
      description: "Posted more than N days after the document date.",
      default_severity: "warning",
      incremental: true,
      has_fix: false,
      params: [param("days", "int", "Days", 7, { minimum: 1, maximum: 365 })],
      enabled: true,
      severity: "warning",
      values: { days },
    },
    {
      code: "NEG_CASH",
      name: "Negative cash or bank balance",
      description: "A bank or cash account went below zero.",
      default_severity: "critical",
      incremental: true,
      has_fix: true,
      params: [
        param("fix_source", "choice", "Fix source", "auto", {
          choices: ["auto", "transfer", "shareholder_loan"],
        }),
        param("shareholder_loan_account", "str", "Shareholder loan account code", "2900"),
      ],
      enabled: true,
      severity: "critical",
      values: { fix_source: "auto", shareholder_loan_account: "2900" },
    },
    {
      code: "ROUND_AMOUNT",
      name: "Round amount journal",
      description: "Journals with round amounts at or above a threshold.",
      default_severity: "info",
      incremental: true,
      has_fix: false,
      params: [
        param("threshold", "decimal", "Threshold", "1000.00", { minimum: "0.00" }),
        param("multiple", "int", "Multiple of", 100, { minimum: 1 }),
      ],
      enabled: roundOn,
      severity: "info",
      values: { threshold: "1000.00", multiple: 100 },
    },
  ];
}

async function mockApi(page: Page) {
  const state = { days: 7, roundOn: true, ranWith: 7 };
  const patches: { code: string; body: Record<string, unknown> }[] = [];
  await mockCsrf(page);
  await page.route(`${API}/`, (r) => r.fulfill({ json: TEARDOWN_SUMMARY }));
  await page.route(`${API}/findings*`, (r) => {
    // Journal 1 was posted 12 days after its date: a finding while N < 12, as the engine does.
    const findings = TEARDOWN_FINDINGS.filter((f) => f.rule !== "BACKDATED" || state.ranWith < 12);
    return r.fulfill({ json: { count: findings.length, findings } });
  });
  await page.route(`${API}/rules`, (r) =>
    r.fulfill({ json: { rules: rules(state.days, state.roundOn) } }),
  );
  await page.route(`${API}/rules/*`, (r) => {
    const code = new URL(r.request().url()).pathname.split("/").pop() ?? "";
    const body = jsonBody(r);
    patches.push({ code, body });
    const params = (body.params ?? {}) as Record<string, unknown>;
    if (code === "BACKDATED" && typeof params.days === "number") state.days = params.days;
    if (code === "ROUND_AMOUNT" && typeof body.enabled === "boolean") state.roundOn = body.enabled;
    const rule = rules(state.days, state.roundOn).find((x) => x.code === code);
    return r.fulfill({ json: { ...rule, ...(body.severity ? { severity: body.severity } : {}) } });
  });
  await page.route(`${API}/run`, (r) => {
    state.ranWith = state.days; // the next run reads the saved settings
    return r.fulfill({ status: 202, json: { job: "job-1" } });
  });
  return { patches };
}

test.use({ viewport: { width: 1440, height: 900 } });

test("changing N is validated, saved and used by the next run", async ({ page }) => {
  const { patches } = await mockApi(page);
  await page.goto(`/o/${ORG}/accounting/assurance`);
  await expect(page.locator('[data-rule-group="BACKDATED"]')).toBeVisible();

  await page.getByRole("tab", { name: "Rule settings" }).click();
  await expect(page).toHaveURL(/\?tab=rules$/);
  const backdated = page.locator('[data-rule="BACKDATED"]');
  const days = backdated.getByLabel("Days");
  await expect(days).toHaveValue("7");
  const save = page.getByRole("button", { name: "Save", exact: true });

  await days.fill("0");
  await expect(backdated.locator("[data-param-error]")).toHaveText("Enter at least 1.");
  await expect(days).toHaveAttribute("aria-invalid", "true");
  await expect(save).toBeDisabled();
  await days.fill("12.5");
  await expect(backdated.locator("[data-param-error]")).toHaveText("Enter a whole number.");
  await days.fill("30");
  await expect(backdated.locator("[data-param-error]")).toHaveCount(0);

  await page.getByRole("switch", { name: "Round amount journal is on" }).uncheck();
  await page.getByLabel("Severity of Backdated posting").selectOption("info");
  await expectAccessible(page);
  await save.click();
  await expect(page.getByRole("status").filter({ hasText: "rules saved" })).toHaveText(
    "2 rules saved. Changes apply on the next run.",
  );
  expect(patches).toEqual([
    { code: "BACKDATED", body: { severity: "info", params: { days: 30 } } },
    { code: "ROUND_AMOUNT", body: { enabled: false } },
  ]);

  // The next run uses N = 30: the 12-day-late journal is no longer flagged.
  await page.getByRole("tab", { name: "Findings" }).click();
  await expect(page.locator('[data-rule-group="BACKDATED"]')).toBeVisible();
  await page.getByRole("button", { name: "Run the rules" }).click();
  await expect(page.locator('[data-rule-group="BACKDATED"]')).toHaveCount(0, { timeout: 10_000 });
  await expect(page.locator('[data-rule-group="NEG_CASH"]')).toBeVisible();
});

test("reset to defaults puts the parameters back", async ({ page }) => {
  const { patches } = await mockApi(page);
  await page.goto(`/o/${ORG}/accounting/assurance?tab=rules`);
  const choice = page.locator('[data-rule="NEG_CASH"]').getByLabel("Fix source");
  await choice.selectOption("shareholder_loan");
  await expect(page.locator('[data-rule="NEG_CASH"]')).toContainText("Changed");
  await page.getByRole("button", { name: "Reset to defaults" }).click();
  await expect(choice).toHaveValue("auto");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  // ROUND_AMOUNT was on already, everything else at its default: nothing to send.
  await expect(page.getByRole("status").filter({ hasText: "Nothing" })).toHaveText(
    "Nothing to save.",
  );
  expect(patches).toEqual([]);
});
