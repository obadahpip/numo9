import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * A-05-T13 — Settings → Lock dates: matrix, impact preview, reason prompt. Acceptance: flow F6 —
 * Settings → Lock dates → GL "Everyone except advisers" = 2026-06-30 → impact preview "3 records
 * not posted…" → Save → the matrix shows the date and the admins are told. Also: moving a lock
 * back asks for a reason (client) and the server's rule (levels out of order) shows in the
 * dialog; axe clean.
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const API = `**/api/v1/o/${ORG}/settings/lock-dates`;
const MODULES = [
  ["gl", "General ledger"],
  ["ar", "Sales and accounts receivable"],
  ["ap", "Purchases and accounts payable"],
  ["bank", "Bank"],
  ["payroll", "Payroll"],
  ["tax", "Sales tax"],
] as const;
const cell = (date: string | null) => ({ date, reason: "", updated_at: null });

function matrix(gl: { advisers_only?: string | null; everyone?: string | null } = {}) {
  return MODULES.map(([module, module_label]) => ({
    module,
    module_label,
    advisers_only: cell(module === "gl" ? (gl.advisers_only ?? null) : null),
    everyone: cell(module === "gl" ? (gl.everyone ?? null) : null),
  }));
}

async function mock(page: Page, start = matrix()) {
  await mockCsrf(page);
  let current = start;
  const sent: Record<string, unknown>[] = [];
  await page.route(API, (route) => {
    if (route.request().method() === "PATCH") {
      const body = jsonBody(route);
      sent.push(body);
      if (body.level === "everyone" && body.date === "2026-07-31")
        return route.fulfill({
          status: 400,
          json: {
            date: [
              "The lock for everyone (2026-07-31) can't be later than the lock for everyone except advisers (2026-06-30).",
            ],
          },
        });
      current = matrix({ advisers_only: body.date as string | null });
      return route.fulfill({ json: current });
    }
    return route.fulfill({ json: current });
  });
  await page.route(`${API}/impact**`, (route) => {
    const url = new URL(route.request().url());
    const date = url.searchParams.get("date")!;
    const count = date >= "2026-06-01" ? 3 : 0;
    return route.fulfill({
      json: {
        module: "gl",
        date,
        items: [
          {
            module: "gl",
            kind: "journals",
            label: "Journal entries not posted (draft or awaiting approval)",
            count,
          },
        ],
        total: count,
      },
    });
  });
  return sent;
}

test.use({ viewport: { width: 1280, height: 1000 } });

test("flow F6: GL lock with impact preview, saved", async ({ page }) => {
  const sent = await mock(page);
  await page.goto(`/o/${ORG}/settings/lock-dates`);
  await expect(page.getByRole("heading", { level: 1, name: "Lock dates" })).toBeVisible();
  await expect(page.locator("[data-lock-module]")).toHaveCount(6);
  await expectAccessible(page);

  await page.getByRole("button", { name: /General ledger, Everyone except advisers$/ }).click();
  const dialog = page.getByRole("dialog", { name: "General ledger — Everyone except advisers" });
  await dialog.getByLabel("Lock date").fill("2026-06-30");
  await expect(dialog.locator("[data-lock-impact]")).toContainText(
    "3 records not posted are dated on or before 2026-06-30: after locking, they can't be posted unless the lock moves back.",
  );
  await expect(dialog.locator("[data-lock-impact]")).toContainText(
    "Journal entries not posted (draft or awaiting approval): 3",
  );
  await expectAccessible(page);
  await dialog.getByRole("button", { name: "Save lock date" }).click();
  await expect(dialog).toBeHidden();
  await expect(
    page.locator('[data-lock-module="gl"] [data-lock-level="advisers_only"]'),
  ).toHaveText("2026-06-30");
  await expect(page.locator("[data-locks-status]")).toHaveText(
    "General ledger lock saved. The organisation's admins were told.",
  );
  expect(sent).toEqual([{ module: "gl", level: "advisers_only", date: "2026-06-30", reason: "" }]);
});

test("moving back asks for a reason; server rules show in the dialog", async ({ page }) => {
  const sent = await mock(page, matrix({ advisers_only: "2026-06-30" }));
  await page.goto(`/o/${ORG}/settings/lock-dates`);
  await page.getByRole("button", { name: /General ledger, Everyone except advisers$/ }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Lock date").fill("2026-05-31");
  await expect(dialog.locator("[data-lock-impact]")).toContainText(
    "Nothing unposted is dated on or before 2026-05-31.",
  );
  await dialog.getByRole("button", { name: "Save lock date" }).click();
  await expect(dialog.getByRole("alert")).toHaveText(
    "Moving the lock back reopens 2026-06-30 and earlier: say why.",
  );
  expect(sent).toEqual([]);
  await dialog.getByLabel("Reason").fill("Late supplier bill for May");
  await dialog.getByRole("button", { name: "Save lock date" }).click();
  await expect(dialog).toBeHidden();
  expect(sent[0]).toMatchObject({ date: "2026-05-31", reason: "Late supplier bill for May" });

  await page.getByRole("button", { name: /General ledger, Everyone$/ }).click();
  const second = page.getByRole("dialog");
  await second.getByLabel("Lock date").fill("2026-07-31");
  await second.getByRole("button", { name: "Save lock date" }).click();
  await expect(second.getByRole("alert")).toContainText(
    "can't be later than the lock for everyone except advisers",
  );
});
