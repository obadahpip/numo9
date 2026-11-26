import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * C-05-T10 — conversion wizard: progress is saved per step on the server; leaving the page and
 * coming back resumes at the saved step. Server side: backend/tests/test_conversion_api.py.
 */
const ORG = "acme";
const STEPS = ["date", "bank", "invoices", "bills", "other", "review"];

function overview(step: string, completed: string[]) {
  return {
    session: {
      id: "s1",
      conversion_date: "2026-01-01",
      status: "draft",
      lock_balances: false,
      step,
      completed_steps: completed,
      finalised_by: null,
      finalised_at: null,
      opening_entry: null,
      corrections: [],
    },
    difference: {
      debits: "0.00",
      credits: "0.00",
      difference: "0.00",
      balanced: true,
      lines: 0,
      controls: [],
      accounts: [],
      warnings: [],
      opening_equity_missing: true,
      reasons: [{ code: "conversion.empty", message: "Enter at least one opening balance." }],
      can_finalise: false,
    },
    steps: STEPS.map((key) => ({ key, label: key })),
    is_adviser: false,
  };
}

export async function mockConversion(page: Page, initial = { step: "bank", completed: ["date"] }) {
  const saved = { ...initial };
  const patches: Record<string, unknown>[] = [];
  await mockCsrf(page);
  await page.route(/\/api\/v1\/o\/acme\/accounts\?.*/, (r) =>
    r.fulfill({ json: { results: [], count: 0 } }),
  );
  await page.route(/\/api\/v1\/o\/acme\/conversion\/lines$/, (r) =>
    r.fulfill({
      json: { lines: [], difference: overview(saved.step, saved.completed).difference },
    }),
  );
  await page.route(/\/api\/v1\/o\/acme\/conversion\/documents(\?.*)?$/, (r) =>
    r.fulfill({ json: { documents: [] } }),
  );
  await page.route(/\/api\/v1\/o\/acme\/conversion\/$/, (r) => {
    if (r.request().method() === "PATCH") {
      const body = jsonBody(r) as { step?: string; completed_steps?: string[] };
      patches.push(body);
      saved.step = body.step ?? saved.step;
      saved.completed = body.completed_steps ?? saved.completed;
    }
    return r.fulfill({ json: overview(saved.step, saved.completed) });
  });
  return { saved, patches };
}

test.use({ viewport: { width: 1440, height: 900 } });

test("leaving and returning resumes at the saved step", async ({ page }) => {
  const { patches } = await mockConversion(page);
  await page.goto(`/o/${ORG}/accounting/conversion`);
  const stepper = page.getByRole("navigation", { name: "Conversion steps" });
  await expect(stepper.locator('[aria-current="step"]')).toHaveAttribute("data-step-key", "bank");
  await expectAccessible(page);
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(stepper.locator('[aria-current="step"]')).toHaveAttribute(
    "data-step-key",
    "invoices",
  );
  expect(patches.at(-1)).toEqual({ step: "invoices", completed_steps: ["date", "bank"] });
  // Leave and come back: the wizard opens on the saved step.
  await page.goto(`/o/${ORG}/home`);
  await page.goto(`/o/${ORG}/accounting/conversion`);
  await expect(stepper.locator('[aria-current="step"]')).toHaveAttribute(
    "data-step-key",
    "invoices",
  );
  await expect(stepper.getByRole("button", { name: "2. Bank and cash (done)" })).toBeVisible();
});

/** C-05-T12 — open invoices grid: paste 20 rows from a spreadsheet → 20 documents validated. */
test("paste 20 rows → 20 documents validated", async ({ page }) => {
  await mockConversion(page, { step: "invoices", completed: ["date", "bank"] });
  const batches: { dry_run: boolean; rows: unknown[] }[] = [];
  await page.route(/\/api\/v1\/o\/acme\/conversion\/documents$/, (r) => {
    if (r.request().method() !== "POST") return r.fulfill({ json: { documents: [] } });
    const body = jsonBody(r) as { dry_run: boolean; rows: unknown[] };
    batches.push(body);
    const rows = body.rows.map((_, i) => ({ row: i + 1, ok: true, errors: [], id: null }));
    return r.fulfill({
      status: body.dry_run ? 200 : 201,
      json: { dry_run: body.dry_run, rows, ok: rows.length, errors: 0, written: 0 },
    });
  });
  await page.goto(`/o/${ORG}/accounting/conversion`);
  const tsv = Array.from(
    { length: 20 },
    (_, i) => `ON Customer Ltd\tINV-${900 + i}\t2025-11-15\t2025-12-15\t${100 + i}.00\t`,
  ).join("\n");
  await page.getByLabel("Customer, row 1").evaluate((input, text) => {
    const data = new DataTransfer();
    data.setData("text/plain", text);
    input.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data, bubbles: true }));
  }, tsv);
  await expect(page.getByText("20 rows pasted.")).toBeVisible();
  await expect(page.locator("[data-grid=invoice] [data-row]")).toHaveCount(20);
  await page.getByRole("button", { name: "Check the rows" }).click();
  await expect(page.getByText("All 20 rows are ready to add.")).toBeVisible();
  expect(batches[0]?.dry_run).toBe(true);
  expect(batches[0]?.rows).toHaveLength(20);
  await expectAccessible(page);
});
